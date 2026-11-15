-- MM_MONTHS.sql -- the totals of each month, kept by triggers, for the ledgers (MM_LEDGER takes what
-- was before a period from them: one row a month, not every move since the first one). Run by
-- INSTALL.sql, which then builds them again from all the moves (rebuild: the moves of before).
--
--   MM_ITEM_MONTH     the stock in and out of an item a month       <- MM_STOCK_MOVE
--   MM_PARTNER_MONTH  the debit and credit of a customer / supplier <- MM_DOC (posted), MM_PAYMENT
--
-- Every change counts: a new row, a row changed (a date moved to another month, a document posted or
-- cancelled, its total, its partner) and a row deleted: what the row was is taken off, what it is now
-- is added. A posted document or payment is what its ledger shows (MM_PARTNER_EVENT).
-- MM_ITEM_MONTH is reservable (as MM_ITEM.STOCK): two tills that sell the same item in the same month do
-- not wait for each other; only the first move of an item in a month makes its row.
create or replace package mm_months as
  -- a move (p_qty: + in, - out) added (p_sign 1) or taken off (-1)
  procedure item_move(p_item_id number, p_at date, p_qty number, p_sign number);
  procedure doc_change(p_doc_type varchar2, p_status varchar2, p_customer_id number, p_supplier_id number,
                       p_date date, p_payment varchar2, p_total number, p_sign number);
  procedure payment_change(p_kind varchar2, p_status varchar2, p_customer_id number, p_supplier_id number,
                           p_date date, p_amount number, p_sign number);
  -- all of it again from the moves, the documents and the payments (INSTALL.sql; no commit). In a
  -- transaction of its own: a row of MM_ITEM_MONTH changed (reservable) and not committed yet cannot
  -- be deleted (ORA-55754)
  procedure rebuild;
end mm_months;
/

create or replace package body mm_months as

  procedure item_move(p_item_id number, p_at date, p_qty number, p_sign number) is
    m date := trunc(p_at, 'MM');
  begin
    if p_item_id is null or nvl(p_qty, 0) = 0 then
      return;
    end if;
    begin
      insert into mm_item_month (item_id, month) values (p_item_id, m);
    exception
      when dup_val_on_index then null;
    end;
    -- reservable: only "col = col + :x where <the primary key>", one column a statement. An "in" taken
    -- off is less in, not more out
    if p_qty > 0 then
      update mm_item_month set qty_in = qty_in + p_sign * p_qty where item_id = p_item_id and month = m;
    else
      update mm_item_month set qty_out = qty_out - p_sign * p_qty where item_id = p_item_id and month = m;
    end if;
  end;

  procedure partner_add(p_kind varchar2, p_id number, p_date date, p_debit number, p_credit number) is
  begin
    if p_id is null or (nvl(p_debit, 0) = 0 and nvl(p_credit, 0) = 0) then
      return;
    end if;
    merge into mm_partner_month t
    using (select p_kind kind, p_id partner_id, trunc(p_date, 'MM') month from dual) s
    on (t.kind = s.kind and t.partner_id = s.partner_id and t.month = s.month)
    when matched then update set t.debit = t.debit + nvl(p_debit, 0), t.credit = t.credit + nvl(p_credit, 0)
    when not matched then insert (kind, partner_id, month, debit, credit)
      values (s.kind, s.partner_id, s.month, nvl(p_debit, 0), nvl(p_credit, 0));
  end;

  -- a document as MM_PARTNER_EVENT counts it (p_sign 1: add it, -1: take it off)
  procedure doc_change(p_doc_type varchar2, p_status varchar2, p_customer_id number, p_supplier_id number,
                       p_date date, p_payment varchar2, p_total number, p_sign number) is
    side varchar2(1);
    ps number;
    dr boolean;                      -- a debit of its partner (as MM_PARTNER_EVENT)
    paid boolean := p_payment in ('CASH', 'CARD');
    deb number;
    cre number;
  begin
    if p_status is null or p_status <> 'P' or nvl(p_total, 0) = 0 then
      return;
    end if;
    select t.side, t.partner_sign into side, ps from mm_doc_type t where t.code = p_doc_type;
    if ps = 0 then
      return;                        -- a note: the stock only, not the balance
    end if;
    dr := ps = case side when 'S' then 1 else -1 end;
    deb := p_sign * ((case when dr then p_total else 0 end) + (case when paid and not dr then p_total else 0 end));
    cre := p_sign * ((case when not dr then p_total else 0 end) + (case when paid and dr then p_total else 0 end));
    if side = 'S' and p_customer_id is not null then
      partner_add('C', p_customer_id, p_date, deb, cre);
    elsif side = 'P' and p_supplier_id is not null then
      partner_add('S', p_supplier_id, p_date, deb, cre);
    end if;
  end;

  procedure payment_change(p_kind varchar2, p_status varchar2, p_customer_id number, p_supplier_id number,
                           p_date date, p_amount number, p_sign number) is
  begin
    if p_status is null or p_status <> 'P' then
      return;
    end if;
    if p_kind = 'R' then
      partner_add('C', p_customer_id, p_date, 0, p_sign * p_amount);
    elsif p_kind = 'P' then
      partner_add('S', p_supplier_id, p_date, p_sign * p_amount, 0);
    end if;
  end;

  procedure rebuild is
  begin
    -- (row by row by its key: a DELETE of the whole of a table with reservable columns ends in ORA-55754
    -- "resource busy" even with nothing pending, while each of its rows by its key goes)
    for r in (select item_id, month from mm_item_month) loop
      delete from mm_item_month where item_id = r.item_id and month = r.month;
    end loop;
    insert into mm_item_month (item_id, month, qty_in, qty_out)
    select item_id, trunc(move_at, 'MM'), sum(case when qty > 0 then qty else 0 end),
           sum(case when qty < 0 then -qty else 0 end)
    from mm_stock_move group by item_id, trunc(move_at, 'MM');
    delete from mm_partner_month;
    insert into mm_partner_month (kind, partner_id, month, debit, credit)
    select kind, partner_id, trunc(ldate, 'MM'), sum(debit), sum(credit)
    from mm_partner_event group by kind, partner_id, trunc(ldate, 'MM');
  end;
end mm_months;
/

create or replace trigger mm_stock_move_month
after insert or delete or update of item_id, qty, move_at on mm_stock_move
for each row
begin
  if updating or deleting then
    mm_months.item_move(:old.item_id, :old.move_at, :old.qty, -1);
  end if;
  if inserting or updating then
    mm_months.item_move(:new.item_id, :new.move_at, :new.qty, 1);
  end if;
end;
/

-- (only what changes what a ledger shows: a draft's lines move its totals without anything here)
create or replace trigger mm_doc_month
after insert or delete or update of status, doc_type, customer_id, supplier_id, doc_date, payment, total on mm_doc
for each row
when (old.status = 'P' or new.status = 'P')
begin
  if updating or deleting then
    mm_months.doc_change(:old.doc_type, :old.status, :old.customer_id, :old.supplier_id, :old.doc_date,
                         :old.payment, :old.total, -1);
  end if;
  if inserting or updating then
    mm_months.doc_change(:new.doc_type, :new.status, :new.customer_id, :new.supplier_id, :new.doc_date,
                         :new.payment, :new.total, 1);
  end if;
end;
/

create or replace trigger mm_payment_month
after insert or delete or update of kind, status, customer_id, supplier_id, pay_date, amount on mm_payment
for each row
begin
  if updating or deleting then
    mm_months.payment_change(:old.kind, :old.status, :old.customer_id, :old.supplier_id, :old.pay_date,
                             :old.amount, -1);
  end if;
  if inserting or updating then
    mm_months.payment_change(:new.kind, :new.status, :new.customer_id, :new.supplier_id, :new.pay_date,
                             :new.amount, 1);
  end if;
end;
/

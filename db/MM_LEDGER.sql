-- MM_LEDGER.sql -- the ledgers (καρτέλες) of an item, a customer and a supplier for a period:
-- the balance before it (from the carry-over), its moves one by one with the running balance, the
-- totals of the period and the balance at its end. Run by INSTALL.sql.
--
--   select * from table(mm_ledger.item_rows(:item_id, :from, :to))           (the reports)
--   select * from table(mm_ledger.partner_rows('C', :customer_id, :from, :to))
--   mm_ledger.fill('I' / 'C' / 'S', id, from, to, open, debit, credit, close)  (the form MM_LEDGER:
--                                                      the rows in MM_LEDGER_ROW, the totals out)
-- The first row (KIND O) is the carry-over, the others (M) the moves.
--   An item:     DEBIT in, CREDIT out, BALANCE the stock (every move of MM_STOCK_MOVE, by its hour).
--   A customer:  DEBIT the invoices, CREDIT the credit notes and the receipts; BALANCE what he owes.
--   A supplier:  CREDIT the invoices, DEBIT the credit notes and the payments; BALANCE what we owe.
-- A document paid at once (cash or card) has a second row, its money: it leaves the balance as it was.
-- Only what is posted: cancelled documents and payments are not in a ledger.
--
-- The reports (reports/MM_LEDGER_I, MM_LEDGER_P): report_rows, the moves with what was before each
-- one (PRIOR_*) and up to it (CUM_*): the first PRIOR_ of a page is its "from the carry-over" (από
-- μεταφορά), the last CUM_ and BALANCE its "to the carry-over" (σε μεταφορά); title and label: the
-- Greek of the report (its XML is ASCII).
create or replace package mm_ledger as
  type t_row is record (
    seq       number,
    kind      varchar2(1),
    ldate     date,
    doc_id    number,
    doc_text  varchar2(40),
    partner   varchar2(100),
    descr     varchar2(200),
    debit     number,
    credit    number,
    balance   number);
  type t_rows is table of t_row;
  type t_rrow is record (
    seq            number,
    kind           varchar2(1),
    ldate          date,
    doc_text       varchar2(40),
    descr          varchar2(300),    -- the partner (or register) and the description
    debit          number,
    credit         number,
    balance        number,
    prior_debit    number,           -- the totals of the period before this row
    prior_credit   number,
    prior_balance  number,
    cum_debit      number,           -- ... with it
    cum_credit     number);
  type t_rrows is table of t_rrow;

  function item_rows(p_item_id number, p_from date, p_to date) return t_rows pipelined;
  -- p_kind: C a customer, S a supplier
  function partner_rows(p_kind varchar2, p_id number, p_from date, p_to date) return t_rows pipelined;
  -- p_what: I an item, C a customer, S a supplier
  procedure fill(p_what varchar2, p_id number, p_from date, p_to date,
                 p_open out number, p_debit out number, p_credit out number, p_close out number);
  -- the rows of a report: the moves (only the carry-over when there are none)
  function report_rows(p_what varchar2, p_id number, p_from date, p_to date) return t_rrows pipelined;
  -- 'Καρτέλα πελάτη: <name>' ...
  function title(p_what varchar2, p_id number) return varchar2;
  -- the words of the reports: DATE, DOC, DESCR, DEBIT, CREDIT, BALANCE (by p_what), FROM_CARRY,
  -- TO_CARRY, TOTALS, OPEN, CLOSE, PAGE, PERIOD, NONE
  function label(p_key varchar2, p_what varchar2 default null) return varchar2;
end mm_ledger;
/

create or replace package body mm_ledger as

  procedure fail(p_no pls_integer, p_text varchar2) is
  begin
    raise_application_error(-20100 - p_no, 'MM-' || to_char(100 + p_no) || ': ' || p_text);
  end;

  procedure check_period(p_id number, p_from date, p_to date) is
  begin
    if p_id is null then
      fail(71, 'Διάλεξε είδος, πελάτη ή προμηθευτή');
    end if;
    if p_from is null or p_to is null or p_from > p_to then
      fail(72, 'Το διάστημα θέλει «από» και «έως», με το «από» πριν από το «έως»');
    end if;
  end;

  function item_rows(p_item_id number, p_from date, p_to date) return t_rows pipelined is
    r t_row;
    bal number;
  begin
    check_period(p_item_id, p_from, p_to);
    select nvl(sum(qty), 0) into bal from mm_stock_move
    where item_id = p_item_id and move_at < trunc(p_from);
    r.seq := 0;
    r.kind := 'O';
    r.ldate := trunc(p_from);
    r.descr := 'Από μεταφορά';
    r.balance := bal;
    pipe row (r);
    for m in (select m.move_at, m.kind, m.qty, m.note, d.id doc_id, d.doc_type, d.doc_no, t.name type_name,
                     nvl(c.name, nvl(s.name, g.name)) partner
              from mm_stock_move m
              left join mm_doc d on d.id = m.doc_id
              left join mm_doc_type t on t.code = d.doc_type
              left join mm_customer c on c.id = d.customer_id
              left join mm_supplier s on s.id = d.supplier_id
              left join mm_register g on g.id = d.register_id
              where m.item_id = p_item_id and m.move_at >= trunc(p_from) and m.move_at < trunc(p_to) + 1
              order by m.move_at, m.id) loop
      r.seq := r.seq + 1;
      r.kind := 'M';
      r.ldate := m.move_at;
      r.doc_id := m.doc_id;
      r.doc_text := case when m.doc_id is not null then m.doc_type || ' ' || m.doc_no end;
      r.partner := m.partner;
      r.descr := case m.kind
                   when 'DOC' then m.type_name || case when m.note is not null then ': ' || m.note end
                   when 'INIT' then nvl(m.note, 'Απογραφή')
                   when 'ASM' then nvl(m.note, 'Συναρμολόγηση')
                   else nvl(m.note, 'Διόρθωση') end;
      r.debit := case when m.qty > 0 then m.qty end;
      r.credit := case when m.qty < 0 then -m.qty end;
      bal := bal + m.qty;
      r.balance := bal;
      pipe row (r);
    end loop;
    return;
  end;

  function partner_rows(p_kind varchar2, p_id number, p_from date, p_to date) return t_rows pipelined is
    r t_row;
    bal number := 0;
    side varchar2(1) := case p_kind when 'C' then 'S' when 'S' then 'P' end;
    sign_ number := case p_kind when 'C' then 1 else -1 end;    -- the balance: debit - credit, or credit - debit
    opened boolean := false;
    pname varchar2(100);
  begin
    if side is null then
      fail(73, 'Καρτέλα πελάτη (C) ή προμηθευτή (S)');
    end if;
    check_period(p_id, p_from, p_to);
    if p_kind = 'C' then
      select max(name) into pname from mm_customer where id = p_id;
    else
      select max(name) into pname from mm_supplier where id = p_id;
    end if;
    r.seq := 0;
    -- the documents (a sale out or a purchase back: debit), the money of those paid at once, the
    -- receipts (credit) and the payments (debit)
    for e in (select d.doc_date ldate, d.created_at at_, d.id doc_id, d.doc_type || ' ' || d.doc_no doc_text,
                     t.name descr, case when t.stock_sign = -1 then d.total end debit,
                     case when t.stock_sign <> -1 then d.total end credit, 1 o
              from mm_doc d join mm_doc_type t on t.code = d.doc_type
              where d.status = 'P' and t.side = side
                and ((p_kind = 'C' and d.customer_id = p_id) or (p_kind = 'S' and d.supplier_id = p_id))
              union all
              select d.doc_date, d.created_at, d.id, d.doc_type || ' ' || d.doc_no,
                     'Εξόφληση με το παραστατικό (' || case d.payment when 'CASH' then 'μετρητά' else 'κάρτα' end || ')',
                     case when t.stock_sign <> -1 then d.total end, case when t.stock_sign = -1 then d.total end, 2
              from mm_doc d join mm_doc_type t on t.code = d.doc_type
              where d.status = 'P' and t.side = side and d.payment in ('CASH', 'CARD')
                and ((p_kind = 'C' and d.customer_id = p_id) or (p_kind = 'S' and d.supplier_id = p_id))
              union all
              select p.pay_date, p.created_at, null, case p.kind when 'R' then 'Είσπραξη' else 'Πληρωμή' end,
                     case p.method when 'CASH' then 'Μετρητά' when 'CARD' then 'Κάρτα' else 'Έμβασμα' end || case when p.notes is not null then ': ' || p.notes end,
                     case when p.kind = 'P' then p.amount end, case when p.kind = 'R' then p.amount end, 3
              from mm_payment p
              where p.status = 'P'
                and ((p_kind = 'C' and p.kind = 'R' and p.customer_id = p_id)
                  or (p_kind = 'S' and p.kind = 'P' and p.supplier_id = p_id))
              order by 1, 8, 2, 3) loop        -- a day: its documents first, then the money
      if e.ldate >= trunc(p_from) and not opened then
        r.kind := 'O';
        r.ldate := trunc(p_from);
        r.descr := 'Από μεταφορά';
        r.partner := pname;
        r.balance := bal;
        pipe row (r);
        opened := true;
      end if;
      exit when e.ldate >= trunc(p_to) + 1;
      bal := bal + sign_ * (nvl(e.debit, 0) - nvl(e.credit, 0));
      if opened then
        r.seq := r.seq + 1;
        r.kind := 'M';
        r.ldate := e.ldate;
        r.doc_id := e.doc_id;
        r.doc_text := e.doc_text;
        r.partner := pname;
        r.descr := e.descr;
        r.debit := e.debit;
        r.credit := e.credit;
        r.balance := bal;
        pipe row (r);
      end if;
    end loop;
    if not opened then
      r.kind := 'O';
      r.ldate := trunc(p_from);
      r.descr := 'Από μεταφορά';
      r.partner := pname;
      r.balance := bal;
      pipe row (r);
    end if;
    return;
  end;

  procedure fill(p_what varchar2, p_id number, p_from date, p_to date,
                 p_open out number, p_debit out number, p_credit out number, p_close out number) is
  begin
    delete from mm_ledger_row;
    if p_what = 'I' then
      insert into mm_ledger_row (seq, kind, ldate, doc_id, doc_text, partner, descr, debit, credit, balance)
      select seq, kind, ldate, doc_id, doc_text, partner, descr, debit, credit, balance
      from table(item_rows(p_id, p_from, p_to));
    elsif p_what in ('C', 'S') then
      insert into mm_ledger_row (seq, kind, ldate, doc_id, doc_text, partner, descr, debit, credit, balance)
      select seq, kind, ldate, doc_id, doc_text, partner, descr, debit, credit, balance
      from table(partner_rows(p_what, p_id, p_from, p_to));
    else
      fail(73, 'Καρτέλα είδους (I), πελάτη (C) ή προμηθευτή (S)');
    end if;
    select max(case when kind = 'O' then balance end), nvl(sum(case when kind = 'M' then debit end), 0),
           nvl(sum(case when kind = 'M' then credit end), 0)
    into p_open, p_debit, p_credit
    from mm_ledger_row;
    p_close := p_open + case when p_what = 'S' then p_credit - p_debit else p_debit - p_credit end;
  end;

  function report_rows(p_what varchar2, p_id number, p_from date, p_to date) return t_rrows pipelined is
    r t_rrow;
    prev number;
    dsum number := 0;
    csum number := 0;
    open_ t_row;
    moves pls_integer := 0;

    procedure out_(x t_row) is
    begin
      r.seq := x.seq;
      r.kind := x.kind;
      r.ldate := x.ldate;
      r.doc_text := x.doc_text;
      r.descr := case when x.partner is not null and p_what = 'I' then x.partner || ' - ' end || x.descr;
      r.debit := x.debit;
      r.credit := x.credit;
      r.balance := x.balance;
      r.prior_debit := dsum;
      r.prior_credit := csum;
      r.prior_balance := prev;
      dsum := dsum + nvl(x.debit, 0);
      csum := csum + nvl(x.credit, 0);
      r.cum_debit := dsum;
      r.cum_credit := csum;
      prev := x.balance;
    end;
  begin
    if p_what = 'I' then
      for x in (select * from table(item_rows(p_id, p_from, p_to))) loop
        if x.kind = 'O' then
          open_.seq := x.seq; open_.kind := x.kind; open_.ldate := x.ldate; open_.descr := x.descr;
          open_.balance := x.balance;
          prev := x.balance;
        else
          moves := moves + 1;
          out_(x);
          pipe row (r);
        end if;
      end loop;
    elsif p_what in ('C', 'S') then
      for x in (select * from table(partner_rows(p_what, p_id, p_from, p_to))) loop
        if x.kind = 'O' then
          open_.seq := x.seq; open_.kind := x.kind; open_.ldate := x.ldate; open_.descr := x.descr;
          open_.balance := x.balance;
          prev := x.balance;
        else
          moves := moves + 1;
          out_(x);
          pipe row (r);
        end if;
      end loop;
    else
      fail(73, 'Καρτέλα είδους (I), πελάτη (C) ή προμηθευτή (S)');
    end if;
    if moves = 0 then
      out_(open_);
      pipe row (r);
    end if;
    return;
  end;

  function title(p_what varchar2, p_id number) return varchar2 is
    v varchar2(300);
  begin
    if p_what = 'I' then
      select max(code || ' ' || name) into v from mm_item where id = p_id;
      return 'Καρτέλα είδους: ' || v;
    elsif p_what = 'C' then
      select max(name || case when afm is not null then ' (ΑΦΜ ' || afm || ')' end) into v from mm_customer where id = p_id;
      return 'Καρτέλα πελάτη: ' || v;
    elsif p_what = 'S' then
      select max(name || case when afm is not null then ' (ΑΦΜ ' || afm || ')' end) into v from mm_supplier where id = p_id;
      return 'Καρτέλα προμηθευτή: ' || v;
    end if;
    return null;
  end;

  function label(p_key varchar2, p_what varchar2 default null) return varchar2 is
  begin
    return case upper(p_key)
      when 'DATE' then 'Ημερομηνία'
      when 'DOC' then 'Παραστατικό'
      when 'DESCR' then case when p_what = 'I' then 'Πελάτης / προμηθευτής / ταμείο - περιγραφή' else 'Περιγραφή' end
      when 'DEBIT' then case when p_what = 'I' then 'Εισαγωγή' else 'Χρέωση' end
      when 'CREDIT' then case when p_what = 'I' then 'Εξαγωγή' else 'Πίστωση' end
      when 'BALANCE' then case when p_what = 'I' then 'Απόθεμα' else 'Υπόλοιπο' end
      when 'FROM_CARRY' then 'Από μεταφορά'
      when 'TO_CARRY' then 'Σε μεταφορά'
      when 'TOTALS' then 'Σύνολα περιόδου'
      when 'OPEN' then 'Από προηγούμενη περίοδο'
      when 'CLOSE' then case when p_what = 'I' then 'Τελικό απόθεμα' else 'Γενικό υπόλοιπο' end
      when 'PAGE' then 'Σελίδα'
      when 'PERIOD' then 'Διάστημα'
      else p_key end;
  end;
end mm_ledger;
/

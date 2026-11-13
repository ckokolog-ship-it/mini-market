-- MM_CORE.sql -- the rules of the mini market, in one package. Everything that writes goes through
-- here: the forms (Oracle Forms), the web pages and the phones (through a REST layer) call the same
-- procedures, so the three behave the same.
--
-- No COMMIT inside: the caller commits (a form at its save, the REST layer at the end of a call).
-- Errors: raise_application_error -20100 .. -20199, the text in Greek, the code first
-- ("MM-104: ..."), so that a form or a web page can show it as it is.
--
-- MM_ITEM.STOCK is reservable: only "stock = stock +/- n where id = :id", and a SELECT in the
-- same transaction still sees the stock before the change (the change is applied at COMMIT).

create or replace package mm_core as

  -- the check digits: 'Y' or 'N' (not boolean: Forms and SQL read them alike)
  function afm_ok(p_afm varchar2) return varchar2;
  function ean_ok(p_code varchar2) return varchar2;

  -- an item by barcode or by code; null if there is none (or it is inactive and p_active = 'Y')
  function find_item(p_code varchar2, p_active varchar2 default 'Y') return number;

  -- net, VAT and total of a line: the price with VAT (p_incl = 'Y') or without
  procedure amounts(p_price number, p_qty number, p_discount number, p_rate number, p_incl varchar2,
                    o_net out number, o_vat out number, o_total out number);

  -- the price a new line takes when none is given: retail with VAT, sale without VAT, or the cost
  function default_price(p_doc_type varchar2, p_item_id number) return number;

  -- the documents: a draft, its lines, then post (number, stock, cash) or cancel
  function new_doc(p_doc_type varchar2, p_customer_id number default null, p_supplier_id number default null,
                   p_register_id number default null, p_payment varchar2 default 'CASH',
                   p_doc_date date default trunc(sysdate)) return number;
  function add_line(p_doc_id number, p_item_id number, p_qty number,
                    p_price number default null, p_discount number default 0) return number;
  procedure update_line(p_line_id number, p_qty number, p_price number, p_discount number default 0);
  procedure delete_line(p_line_id number);
  procedure recalc(p_doc_id number);
  procedure delete_doc(p_doc_id number);                 -- a draft only
  function post_doc(p_doc_id number) return number;     -- returns the number of the document
  procedure cancel_doc(p_doc_id number);                 -- a posted one, while its Z is open
  function credit_note(p_doc_id number) return number;  -- a draft PPY/PAG with the lines of an invoice

  -- the stock by hand
  procedure adjust_stock(p_item_id number, p_qty number, p_note varchar2);

  -- the cash register: one open Z at a time
  function open_z(p_register_id number, p_cash number default 0) return number;
  procedure cash_in_out(p_register_id number, p_amount number, p_note varchar2); -- + in, - out
  function open_z_of(p_register_id number) return number;  -- null when closed
  function close_z(p_register_id number) return number;    -- returns the id of the Z

  -- the cards with serial numbers (items with SERIAL_TRACKED = 'Y'); the PIN is kept encrypted
  function load_serial(p_item_id number, p_serial varchar2, p_pin varchar2 default null,
                       p_note varchar2 default null) return number;     -- straight to the stock (+1)
  function add_serial(p_line_id number, p_serial varchar2, p_pin varchar2 default null) return number;
                                                                         -- to a line of a draft purchase
  function sell_serial(p_doc_id number, p_item_id number default null,
                       p_serial varchar2 default null) return number;   -- the oldest available, or this one
  procedure release_serial(p_serial_id number);                         -- back from a draft sale
  function reveal_pin(p_serial_id number, p_user varchar2 default null) return varchar2;
  function receipt_pin(p_serial_id number) return varchar2;             -- a card sold today

  -- the count of the stock: start, scan (from the phones), post
  function start_count(p_name varchar2) return number;
  function scan(p_count_id number, p_code varchar2, p_qty number default 1,
                p_mode varchar2 default 'ADD', p_device varchar2 default null) return number;
  procedure post_count(p_count_id number);
  procedure cancel_count(p_count_id number);

end mm_core;
/

create or replace package body mm_core as

  procedure fail(p_no pls_integer, p_text varchar2) is
  begin
    raise_application_error(-20100 - p_no, 'MM-' || to_char(100 + p_no) || ': ' || p_text);
  end;

  function tracked(p_item_id number) return boolean is
    v varchar2(1);
  begin
    select serial_tracked into v from mm_item where id = p_item_id;
    return v = 'Y';
  exception
    when no_data_found then return false;
  end;

  -- the cards of a line of a draft: a sale gives them back, a purchase forgets them
  procedure release_line(p_line_id number) is
  begin
    update mm_serial set status = 'A', out_line_id = null, out_doc_id = null
    where out_line_id = p_line_id and status = 'R';
    delete from mm_serial where in_line_id = p_line_id and status = 'N';
  end;

  -- ---------------------------------------------------------------------------------------------
  function afm_ok(p_afm varchar2) return varchar2 is
    s pls_integer := 0;
  begin
    if p_afm is null or not regexp_like(p_afm, '^[0-9]{9}$') or p_afm = '000000000' then
      return 'N';
    end if;
    for i in 1 .. 8 loop
      s := s + to_number(substr(p_afm, i, 1)) * power(2, 9 - i);
    end loop;
    return case when mod(mod(s, 11), 10) = to_number(substr(p_afm, 9, 1)) then 'Y' else 'N' end;
  end;

  function ean_ok(p_code varchar2) return varchar2 is
    s pls_integer := 0;
    n pls_integer;
  begin
    if p_code is null or not regexp_like(p_code, '^([0-9]{8}|[0-9]{12,14})$') then
      return 'N';
    end if;
    n := length(p_code);
    -- from the right, without the check digit: 3, 1, 3, ...
    for i in 1 .. n - 1 loop
      s := s + to_number(substr(p_code, n - i, 1)) * case when mod(i, 2) = 1 then 3 else 1 end;
    end loop;
    return case when mod(10 - mod(s, 10), 10) = to_number(substr(p_code, n, 1)) then 'Y' else 'N' end;
  end;

  function find_item(p_code varchar2, p_active varchar2 default 'Y') return number is
    v number;
  begin
    select min(id) into v from mm_item
    where (barcode = trim(p_code) or code = upper(trim(p_code)))
      and (p_active = 'N' or active = 'Y');
    return v;
  end;

  -- ---------------------------------------------------------------------------------------------
  procedure amounts(p_price number, p_qty number, p_discount number, p_rate number, p_incl varchar2,
                    o_net out number, o_vat out number, o_total out number) is
    g number := round(p_price * p_qty * (1 - nvl(p_discount, 0) / 100), 2);
  begin
    if p_incl = 'Y' then
      o_total := g;
      o_net := round(g / (1 + p_rate / 100), 2);
      o_vat := o_total - o_net;
    else
      o_net := g;
      o_vat := round(g * p_rate / 100, 2);
      o_total := o_net + o_vat;
    end if;
  end;

  function doc_type_row(p_code varchar2) return mm_doc_type%rowtype is
    t mm_doc_type%rowtype;
  begin
    select * into t from mm_doc_type where code = p_code;
    return t;
  exception
    when no_data_found then fail(1, 'Άγνωστο είδος παραστατικού ' || p_code);
  end;

  function default_price(p_doc_type varchar2, p_item_id number) return number is
    t mm_doc_type%rowtype := doc_type_row(p_doc_type);
    i mm_item%rowtype;
    r number;
  begin
    select * into i from mm_item where id = p_item_id;
    if t.side = 'P' then
      return i.cost;
    elsif t.prices_incl_vat = 'Y' then
      return i.price;
    end if;
    select rate into r from mm_vat where code = i.vat_code;
    return round(i.price / (1 + r / 100), 4);
  end;

  -- the document locked, for a change: it must be a draft
  function draft(p_doc_id number) return mm_doc%rowtype is
    d mm_doc%rowtype;
  begin
    select * into d from mm_doc where id = p_doc_id for update;
    if d.status <> 'D' then
      fail(2, 'Το παραστατικό ' || d.doc_type || ' ' || d.doc_no || ' δεν είναι πρόχειρο');
    end if;
    return d;
  exception
    when no_data_found then fail(3, 'Δεν υπάρχει παραστατικό ' || p_doc_id);
  end;

  -- ---------------------------------------------------------------------------------------------
  function new_doc(p_doc_type varchar2, p_customer_id number default null, p_supplier_id number default null,
                   p_register_id number default null, p_payment varchar2 default 'CASH',
                   p_doc_date date default trunc(sysdate)) return number is
    t mm_doc_type%rowtype := doc_type_row(p_doc_type);
    v number;
  begin
    if t.side = 'S' and p_supplier_id is not null or t.side = 'P' and p_customer_id is not null then
      fail(4, 'Το ' || t.name || ' θέλει ' || case t.side when 'S' then 'πελάτη' else 'προμηθευτή' end);
    end if;
    if t.side = 'P' and p_register_id is not null then
      fail(5, 'Οι αγορές δεν περνούν από ταμείο');
    end if;
    insert into mm_doc (doc_type, customer_id, supplier_id, register_id, payment, doc_date)
    values (p_doc_type, p_customer_id, p_supplier_id, p_register_id, p_payment, p_doc_date)
    returning id into v;
    return v;
  end;

  procedure recalc(p_doc_id number) is
  begin
    update mm_doc d
    set (net, vat, total) = (select nvl(sum(l.net), 0), nvl(sum(l.vat), 0), nvl(sum(l.total), 0)
                             from mm_doc_line l where l.doc_id = d.id)
    where d.id = p_doc_id;
  end;

  function add_line(p_doc_id number, p_item_id number, p_qty number,
                    p_price number default null, p_discount number default 0) return number is
    d mm_doc%rowtype := draft(p_doc_id);
    t mm_doc_type%rowtype := doc_type_row(d.doc_type);
    i mm_item%rowtype;
    r number;
    p number;
    n number; v number; tot number;
    ln number;
    id_ number;
  begin
    begin
      select * into i from mm_item where id = p_item_id;
    exception
      when no_data_found then fail(6, 'Δεν υπάρχει είδος ' || p_item_id);
    end;
    if i.active = 'N' then
      fail(7, 'Το είδος ' || i.code || ' δεν είναι ενεργό');
    end if;
    if i.serial_tracked = 'Y' and not (t.side = 'P' and t.stock_sign = 1) then
      fail(27, 'Το ' || i.code || ' έχει serials: πώληση με sell_serial, φόρτωση με τιμολόγιο αγοράς');
    end if;
    select rate into r from mm_vat where code = i.vat_code;
    p := nvl(p_price, default_price(d.doc_type, p_item_id));
    amounts(p, p_qty, p_discount, r, t.prices_incl_vat, n, v, tot);
    select nvl(max(line_no), 0) + 1 into ln from mm_doc_line where doc_id = p_doc_id;
    insert into mm_doc_line (doc_id, line_no, item_id, qty, price, discount, vat_code, vat_rate, net, vat, total)
    values (p_doc_id, ln, p_item_id, p_qty, p, nvl(p_discount, 0), i.vat_code, r, n, v, tot)
    returning id into id_;
    recalc(p_doc_id);
    return id_;
  end;

  procedure update_line(p_line_id number, p_qty number, p_price number, p_discount number default 0) is
    l mm_doc_line%rowtype;
    d mm_doc%rowtype;
    n number; v number; tot number;
  begin
    select * into l from mm_doc_line where id = p_line_id;
    d := draft(l.doc_id);
    if tracked(l.item_id) and p_qty <> l.qty then
      fail(26, 'Η ποσότητα ενός είδους με serials αλλάζει με τα serials');
    end if;
    amounts(p_price, p_qty, p_discount, l.vat_rate, doc_type_row(d.doc_type).prices_incl_vat, n, v, tot);
    update mm_doc_line
    set qty = p_qty, price = p_price, discount = nvl(p_discount, 0), net = n, vat = v, total = tot
    where id = p_line_id;
    recalc(l.doc_id);
  exception
    when no_data_found then fail(8, 'Δεν υπάρχει γραμμή ' || p_line_id);
  end;

  procedure delete_line(p_line_id number) is
    l mm_doc_line%rowtype;
    d mm_doc%rowtype;
  begin
    select * into l from mm_doc_line where id = p_line_id;
    d := draft(l.doc_id);
    release_line(p_line_id);
    delete from mm_doc_line where id = p_line_id;
    recalc(l.doc_id);
  exception
    when no_data_found then fail(8, 'Δεν υπάρχει γραμμή ' || p_line_id);
  end;

  procedure delete_doc(p_doc_id number) is
    d mm_doc%rowtype := draft(p_doc_id);
  begin
    for l in (select id from mm_doc_line where doc_id = p_doc_id) loop
      release_line(l.id);
    end loop;
    delete from mm_doc where id = p_doc_id;
  end;

  -- ---------------------------------------------------------------------------------------------
  procedure stock_move(p_item_id number, p_kind varchar2, p_qty number, p_doc_id number default null,
                       p_line_id number default null, p_note varchar2 default null,
                       p_count_id number default null) is
  begin
    if p_qty = 0 then
      return;
    end if;
    insert into mm_stock_move (item_id, kind, qty, doc_id, doc_line_id, note, count_id)
    values (p_item_id, p_kind, p_qty, p_doc_id, p_line_id, p_note, p_count_id);
    update mm_item set stock = stock + p_qty where id = p_item_id;   -- reservable: no row lock
  end;

  function open_z_of(p_register_id number) return number is
    v number;
  begin
    select min(id) into v from mm_z where register_id = p_register_id and status = 'O';
    return v;
  end;

  function post_doc(p_doc_id number) return number is
    d mm_doc%rowtype := draft(p_doc_id);
    t mm_doc_type%rowtype;
    no_ number;
    z number;
    lines number;
  begin
    -- the number: the row of the kind locked until the commit, so the numbers have no gaps
    select * into t from mm_doc_type where code = d.doc_type for update;
    select count(*) into lines from mm_doc_line where doc_id = p_doc_id;
    if lines = 0 then
      fail(9, 'Το παραστατικό δεν έχει γραμμές');
    end if;
    if t.partner_needed = 'Y' and d.customer_id is null and d.supplier_id is null then
      fail(4, 'Το ' || t.name || ' θέλει ' || case t.side when 'S' then 'πελάτη' else 'προμηθευτή' end);
    end if;
    if t.code = 'ALP' and d.register_id is null then
      fail(10, 'Η απόδειξη λιανικής θέλει ταμείο');
    end if;
    if t.code = 'ALP' and d.payment = 'CREDIT' then
      fail(11, 'Η απόδειξη λιανικής πληρώνεται με μετρητά ή κάρτα');
    end if;
    if d.register_id is not null then
      z := open_z_of(d.register_id);
      if z is null then
        fail(12, 'Το ταμείο δεν έχει ανοιχτό Ζ');
      end if;
    end if;
    -- a line of cards: as many serials as its quantity
    for l in (select l.id, l.qty, i.code from mm_doc_line l join mm_item i on i.id = l.item_id
              where l.doc_id = p_doc_id and i.serial_tracked = 'Y') loop
      select count(*) into lines from mm_serial where in_line_id = l.id or out_line_id = l.id;
      if lines <> l.qty then
        fail(28, 'Το ' || l.code || ': ' || l.qty || ' τεμάχια, ' || lines || ' serials');
      end if;
    end loop;
    no_ := t.next_no;
    update mm_doc_type set next_no = next_no + 1 where code = t.code;
    recalc(p_doc_id);
    update mm_doc set doc_no = no_, status = 'P', z_id = z where id = p_doc_id
    returning total into d.total;

    for l in (select * from mm_doc_line where doc_id = p_doc_id) loop
      stock_move(l.item_id, 'DOC', t.stock_sign * l.qty, p_doc_id, l.id);
      if t.side = 'P' and t.stock_sign = 1 and l.qty > 0 then
        update mm_item set cost = round(l.net / l.qty, 4) where id = l.item_id;   -- the last cost
      end if;
    end loop;
    update mm_serial set status = 'A' where in_doc_id = p_doc_id and status = 'N';
    update mm_serial set status = 'S', sold_at = sysdate where out_doc_id = p_doc_id and status = 'R';

    if z is not null and d.payment in ('CASH', 'CARD') then
      insert into mm_cash_move (register_id, z_id, kind, payment, amount, doc_id)
      values (d.register_id, z, case when t.stock_sign > 0 then 'REFUND' else 'SALE' end, d.payment,
              case when t.stock_sign > 0 then -d.total else d.total end, p_doc_id);
    end if;
    return no_;
  end;

  procedure cancel_doc(p_doc_id number) is
    d mm_doc%rowtype;
    t mm_doc_type%rowtype;
    zs varchar2(1);
    lines number;
  begin
    begin
      select * into d from mm_doc where id = p_doc_id for update;
    exception
      when no_data_found then fail(3, 'Δεν υπάρχει παραστατικό ' || p_doc_id);
    end;
    if d.status <> 'P' then
      fail(13, 'Ακυρώνεται μόνο καταχωρημένο παραστατικό');
    end if;
    if d.z_id is not null then
      select status into zs from mm_z where id = d.z_id;
      if zs = 'C' then
        fail(14, 'Το Ζ του παραστατικού έχει κλείσει: κάνε πιστωτικό');
      end if;
    end if;
    t := doc_type_row(d.doc_type);
    select count(*) into lines from mm_serial where in_doc_id = p_doc_id and status <> 'A';
    if lines > 0 then
      fail(30, 'Από τις κάρτες αυτής της αγοράς έχουν πουληθεί ή δεσμευτεί ' || lines);
    end if;
    for l in (select * from mm_doc_line where doc_id = p_doc_id) loop
      stock_move(l.item_id, 'DOC', -t.stock_sign * l.qty, p_doc_id, l.id, 'Ακύρωση');
    end loop;
    update mm_serial set status = 'X' where in_doc_id = p_doc_id;
    update mm_serial set status = 'A', sold_at = null, out_line_id = null, out_doc_id = null
    where out_doc_id = p_doc_id and status = 'S';
    insert into mm_cash_move (register_id, z_id, kind, payment, amount, doc_id, note)
    select register_id, z_id, case kind when 'SALE' then 'REFUND' else 'SALE' end, payment, -amount, doc_id, 'Ακύρωση'
    from mm_cash_move where doc_id = p_doc_id and kind in ('SALE', 'REFUND');
    update mm_doc set status = 'C' where id = p_doc_id;
  end;

  function credit_note(p_doc_id number) return number is
    d mm_doc%rowtype;
    c varchar2(3);
    v number;
  begin
    begin
      select * into d from mm_doc where id = p_doc_id;
    exception
      when no_data_found then fail(3, 'Δεν υπάρχει παραστατικό ' || p_doc_id);
    end;
    -- a retail receipt is cancelled (cancel_doc) while its Z is open
    c := case d.doc_type when 'TPY' then 'PPY' when 'TAG' then 'PAG' end;
    if c is null or d.status <> 'P' then
      fail(15, 'Πιστωτικό γίνεται μόνο για καταχωρημένο τιμολόγιο');
    end if;
    select count(*) into v from mm_doc_line l join mm_item i on i.id = l.item_id
    where l.doc_id = p_doc_id and i.serial_tracked = 'Y';
    if v > 0 then
      fail(29, 'Το παραστατικό έχει κάρτες με serials: ακύρωσέ το (όσο το Ζ είναι ανοιχτό)');
    end if;
    v := new_doc(c, d.customer_id, d.supplier_id, d.register_id, d.payment);
    update mm_doc set ref_doc_id = p_doc_id where id = v;
    insert into mm_doc_line (doc_id, line_no, item_id, qty, price, discount, vat_code, vat_rate, net, vat, total)
    select v, line_no, item_id, qty, price, discount, vat_code, vat_rate, net, vat, total
    from mm_doc_line where doc_id = p_doc_id;
    recalc(v);
    return v;
  end;

  procedure adjust_stock(p_item_id number, p_qty number, p_note varchar2) is
  begin
    if p_note is null then
      fail(16, 'Η διόρθωση αποθέματος θέλει αιτιολογία');
    end if;
    if tracked(p_item_id) then
      fail(33, 'Το απόθεμα ενός είδους με serials αλλάζει με τα serials (load_serial)');
    end if;
    stock_move(p_item_id, 'ADJ', p_qty, p_note => p_note);
  end;

  -- ---------------------------------------------------------------------------------------------
  function open_z(p_register_id number, p_cash number default 0) return number is
    n number;
    v number;
  begin
    -- the register locked: two opens at once wait for each other
    begin
      select id into n from mm_register where id = p_register_id and active = 'Y' for update;
    exception
      when no_data_found then fail(17, 'Δεν υπάρχει ενεργό ταμείο ' || p_register_id);
    end;
    if open_z_of(p_register_id) is not null then
      fail(18, 'Το ταμείο έχει ήδη ανοιχτό Ζ');
    end if;
    select nvl(max(z_no), 0) + 1 into n from mm_z where register_id = p_register_id;
    insert into mm_z (register_id, z_no) values (p_register_id, n) returning id into v;
    if nvl(p_cash, 0) <> 0 then
      insert into mm_cash_move (register_id, z_id, kind, amount, note)
      values (p_register_id, v, 'OPEN', p_cash, 'Αρχικό ταμείο');
    end if;
    return v;
  end;

  procedure cash_in_out(p_register_id number, p_amount number, p_note varchar2) is
    z number := open_z_of(p_register_id);
  begin
    if z is null then
      fail(12, 'Το ταμείο δεν έχει ανοιχτό Ζ');
    end if;
    if nvl(p_amount, 0) = 0 or p_note is null then
      fail(19, 'Η κίνηση ταμείου θέλει ποσό και αιτιολογία');
    end if;
    insert into mm_cash_move (register_id, z_id, kind, amount, note)
    values (p_register_id, z, case when p_amount > 0 then 'IN' else 'OUT' end, p_amount, p_note);
  end;

  function close_z(p_register_id number) return number is
    z number;
    n number;
  begin
    begin
      select id into z from mm_z where register_id = p_register_id and status = 'O' for update;
    exception
      when no_data_found then fail(12, 'Το ταμείο δεν έχει ανοιχτό Ζ');
    end;
    select count(*) into n from mm_doc where register_id = p_register_id and status = 'D';
    if n > 0 then
      fail(20, 'Υπάρχουν πρόχειρα παραστατικά στο ταμείο: καταχώρισέ τα ή σβήσε τα');
    end if;
    -- the sales with sign: a credit note takes off
    delete from mm_z_vat where z_id = z;
    insert into mm_z_vat (z_id, vat_code, net, vat, total)
    select z, l.vat_code, sum(-t.stock_sign * l.net), sum(-t.stock_sign * l.vat), sum(-t.stock_sign * l.total)
    from mm_doc d join mm_doc_type t on t.code = d.doc_type join mm_doc_line l on l.doc_id = d.id
    where d.z_id = z and d.status = 'P'
    group by l.vat_code;
    update mm_z m
    set (docs, net, vat, total) =
          (select count(*), nvl(sum(-t.stock_sign * d.net), 0), nvl(sum(-t.stock_sign * d.vat), 0),
                  nvl(sum(-t.stock_sign * d.total), 0)
           from mm_doc d join mm_doc_type t on t.code = d.doc_type
           where d.z_id = m.id and d.status = 'P'),
        (cash, card) =
          (select nvl(sum(case when payment = 'CASH' then amount end), 0),
                  nvl(sum(case when payment = 'CARD' then amount end), 0)
           from mm_cash_move where z_id = m.id and kind in ('SALE', 'REFUND')),
        status = 'C', closed_at = greatest(sysdate, opened_at)
    where m.id = z;
    return z;
  end;

  -- ---------------------------------------------------------------------------------------------
  procedure check_serial(p_item_id number, p_serial varchar2, p_pin varchar2) is
  begin
    if not tracked(p_item_id) then
      fail(25, 'Το είδος ' || p_item_id || ' δεν έχει serials');
    end if;
    if p_serial is null or not regexp_like(p_serial, '^[0-9A-Za-z-]{4,40}$') then
      fail(34, 'Λάθος serial: 4 έως 40 γράμματα, ψηφία ή -');
    end if;
    if p_pin is not null and not regexp_like(p_pin, '^[0-9]{4,20}$') then
      fail(35, 'Λάθος PIN: 4 έως 20 ψηφία');
    end if;
  end;

  function new_serial(p_item_id number, p_serial varchar2, p_pin varchar2, p_status varchar2,
                      p_doc_id number, p_line_id number) return number is
    v number;
  begin
    check_serial(p_item_id, p_serial, p_pin);
    insert into mm_serial (item_id, serial, pin_enc, status, in_doc_id, in_line_id)
    values (p_item_id, p_serial, mm_pin.enc(p_pin), p_status, p_doc_id, p_line_id)
    returning id into v;
    return v;
  exception
    when dup_val_on_index then fail(36, 'Το serial ' || p_serial || ' υπάρχει ήδη');
  end;

  function load_serial(p_item_id number, p_serial varchar2, p_pin varchar2 default null,
                       p_note varchar2 default null) return number is
    v number := new_serial(p_item_id, p_serial, p_pin, 'A', null, null);
  begin
    stock_move(p_item_id, 'ADJ', 1, p_note => nvl(p_note, 'Serial ' || p_serial));
    return v;
  end;

  function add_serial(p_line_id number, p_serial varchar2, p_pin varchar2 default null) return number is
    l mm_doc_line%rowtype;
    d mm_doc%rowtype;
    t mm_doc_type%rowtype;
  begin
    begin
      select * into l from mm_doc_line where id = p_line_id;
    exception
      when no_data_found then fail(8, 'Δεν υπάρχει γραμμή ' || p_line_id);
    end;
    d := draft(l.doc_id);
    t := doc_type_row(d.doc_type);
    if not (t.side = 'P' and t.stock_sign = 1) then
      fail(37, 'Τα serials φορτώνονται σε τιμολόγιο αγοράς');
    end if;
    return new_serial(l.item_id, p_serial, p_pin, 'N', l.doc_id, p_line_id);
  end;

  function sell_serial(p_doc_id number, p_item_id number default null,
                       p_serial varchar2 default null) return number is
    d mm_doc%rowtype := draft(p_doc_id);
    t mm_doc_type%rowtype := doc_type_row(d.doc_type);
    sid number;
    it number;
    ln mm_doc_line%rowtype;
    found boolean := false;
    n number; v number; tot number;
    cursor c is
      select id, item_id from mm_serial
      where status = 'A'
        and (p_item_id is null or item_id = p_item_id)
        and (p_serial is null or serial = p_serial)
      order by id
      for update skip locked;     -- two tills never take the same card
  begin
    if not (t.side = 'S' and t.stock_sign = -1) then
      fail(38, 'Οι κάρτες πουλιούνται με απόδειξη ή τιμολόγιο πώλησης');
    end if;
    if p_item_id is null and p_serial is null then
      fail(39, 'Δώσε είδος ή serial');
    end if;
    open c;
    fetch c into sid, it;
    close c;
    if sid is null then
      fail(40, 'Δεν υπάρχει διαθέσιμη κάρτα' || case when p_serial is not null then ' με serial ' || p_serial end);
    end if;
    -- the line of this item in the document: one more, or a new one
    for r in (select * from mm_doc_line where doc_id = p_doc_id and item_id = it order by line_no) loop
      ln := r;
      found := true;
      exit;
    end loop;
    if found then
      amounts(ln.price, ln.qty + 1, ln.discount, ln.vat_rate, t.prices_incl_vat, n, v, tot);
      update mm_doc_line set qty = qty + 1, net = n, vat = v, total = tot where id = ln.id;
      recalc(p_doc_id);
    else
      -- add_line refuses an item with serials in a sale: the line is made here
      declare
        i mm_item%rowtype;
        r number;
        p number;
        no_ number;
      begin
        select * into i from mm_item where id = it;
        if i.active = 'N' then
          fail(7, 'Το είδος ' || i.code || ' δεν είναι ενεργό');
        end if;
        select rate into r from mm_vat where code = i.vat_code;
        p := default_price(d.doc_type, it);
        amounts(p, 1, 0, r, t.prices_incl_vat, n, v, tot);
        select nvl(max(line_no), 0) + 1 into no_ from mm_doc_line where doc_id = p_doc_id;
        insert into mm_doc_line (doc_id, line_no, item_id, qty, price, discount, vat_code, vat_rate, net, vat, total)
        values (p_doc_id, no_, it, 1, p, 0, i.vat_code, r, n, v, tot)
        returning id into ln.id;
        recalc(p_doc_id);
      end;
    end if;
    update mm_serial set status = 'R', out_line_id = ln.id, out_doc_id = p_doc_id where id = sid;
    return sid;
  end;

  procedure release_serial(p_serial_id number) is
    s mm_serial%rowtype;
    l mm_doc_line%rowtype;
    d mm_doc%rowtype;
    n number; v number; tot number;
  begin
    begin
      select * into s from mm_serial where id = p_serial_id;
    exception
      when no_data_found then fail(41, 'Δεν υπάρχει κάρτα ' || p_serial_id);
    end;
    if s.status <> 'R' then
      fail(42, 'Η κάρτα δεν είναι δεσμευμένη σε πρόχειρο');
    end if;
    select * into l from mm_doc_line where id = s.out_line_id;
    d := draft(l.doc_id);
    update mm_serial set status = 'A', out_line_id = null, out_doc_id = null where id = p_serial_id;
    if l.qty <= 1 then
      delete from mm_doc_line where id = l.id;
    else
      amounts(l.price, l.qty - 1, l.discount, l.vat_rate, doc_type_row(d.doc_type).prices_incl_vat, n, v, tot);
      update mm_doc_line set qty = qty - 1, net = n, vat = v, total = tot where id = l.id;
    end if;
    recalc(l.doc_id);
  end;

  function pin_of(p_serial_id number, p_user varchar2, p_reason varchar2) return varchar2 is
    e raw(64);
  begin
    select pin_enc into e from mm_serial where id = p_serial_id;
    insert into mm_pin_log (serial_id, username, reason) values (p_serial_id, p_user, p_reason);
    return mm_pin.dec(e);
  exception
    when no_data_found then fail(41, 'Δεν υπάρχει κάρτα ' || p_serial_id);
  end;

  -- the PIN for a user who may see it; every time in MM_PIN_LOG. The user: the name given, or the
  -- CLIENT_IDENTIFIER of the session (the login of step 7a sets it)
  function reveal_pin(p_serial_id number, p_user varchar2 default null) return varchar2 is
    u varchar2(60) := upper(nvl(p_user, sys_context('USERENV', 'CLIENT_IDENTIFIER')));
    n number;
  begin
    select count(*) into n from mm_pin_user where username = u;
    if u is null or n = 0 then
      fail(43, 'Δεν έχεις δικαίωμα να δεις το PIN');
    end if;
    return pin_of(p_serial_id, u, 'REVEAL');
  end;

  -- the PIN on the receipt: only of a card sold today, by a posted document
  function receipt_pin(p_serial_id number) return varchar2 is
    n number;
  begin
    select count(*) into n from mm_serial s join mm_doc d on d.id = s.out_doc_id
    where s.id = p_serial_id and s.status = 'S' and d.status = 'P' and s.sold_at >= trunc(sysdate);
    if n = 0 then
      fail(44, 'Το PIN τυπώνεται μόνο για κάρτα που πουλήθηκε σήμερα');
    end if;
    return pin_of(p_serial_id, nvl(upper(sys_context('USERENV', 'CLIENT_IDENTIFIER')), 'RECEIPT'), 'RECEIPT');
  end;

  -- ---------------------------------------------------------------------------------------------
  function open_count(p_count_id number) return mm_count%rowtype is
    c mm_count%rowtype;
  begin
    select * into c from mm_count where id = p_count_id;
    if c.status <> 'O' then
      fail(21, 'Η απογραφή ' || c.name || ' δεν είναι ανοιχτή');
    end if;
    return c;
  exception
    when no_data_found then fail(22, 'Δεν υπάρχει απογραφή ' || p_count_id);
  end;

  function start_count(p_name varchar2) return number is
    v number;
  begin
    insert into mm_count (name) values (nvl(p_name, 'Απογραφή ' || to_char(sysdate, 'dd/mm/yyyy')))
    returning id into v;
    return v;
  end;

  function scan(p_count_id number, p_code varchar2, p_qty number default 1,
                p_mode varchar2 default 'ADD', p_device varchar2 default null) return number is
    c mm_count%rowtype := open_count(p_count_id);
    it number := find_item(p_code, 'N');
    st number;
  begin
    if it is null then
      fail(23, 'Δεν βρέθηκε είδος με κωδικό ' || p_code);
    end if;
    if tracked(it) then
      fail(31, 'Τα είδη με serials δεν μετριούνται στην απογραφή: το απόθεμά τους είναι οι κάρτες τους');
    end if;
    if p_mode not in ('ADD', 'SET') or p_qty is null or p_qty < 0 then
      fail(24, 'Λάθος ποσότητα ή τρόπος (ADD/SET)');
    end if;
    select stock into st from mm_item where id = it;
    -- a second phone on the same item waits only for this row, not for the item
    merge into mm_count_line l
    using (select p_count_id count_id, it item_id from dual) s
    on (l.count_id = s.count_id and l.item_id = s.item_id)
    when matched then update set
      counted_qty = case p_mode when 'ADD' then l.counted_qty + p_qty else p_qty end,
      scanned_at = sysdate, device = nvl(p_device, l.device)
    when not matched then insert (count_id, item_id, counted_qty, system_qty, device)
      values (p_count_id, it, p_qty, st, p_device);
    return it;
  end;

  procedure post_count(p_count_id number) is
    c mm_count%rowtype;
  begin
    select * into c from mm_count where id = p_count_id for update;
    c := open_count(p_count_id);
    for l in (select * from mm_count_line where count_id = p_count_id) loop
      stock_move(l.item_id, 'ADJ', l.counted_qty - l.system_qty, p_note => c.name, p_count_id => p_count_id);
    end loop;
    update mm_count set status = 'P', posted_at = sysdate where id = p_count_id;
  exception
    when no_data_found then fail(22, 'Δεν υπάρχει απογραφή ' || p_count_id);
  end;

  procedure cancel_count(p_count_id number) is
    c mm_count%rowtype := open_count(p_count_id);
  begin
    update mm_count set status = 'C' where id = p_count_id;
  end;

end mm_core;
/

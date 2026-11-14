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

  -- the price a new line takes when none is given: retail with VAT (receipt), the wholesale price
  -- (invoice of sale; empty: the retail without its VAT), or the cost (purchase)
  function default_price(p_doc_type varchar2, p_item_id number) return number;

  -- the documents: a draft, its lines, then post (number, stock, cash) or cancel
  function new_doc(p_doc_type varchar2, p_customer_id number default null, p_supplier_id number default null,
                   p_register_id number default null, p_payment varchar2 default 'CASH',
                   p_doc_date date default trunc(sysdate)) return number;
  function add_line(p_doc_id number, p_item_id number, p_qty number,
                    p_price number default null, p_discount number default 0) return number;
  procedure update_line(p_line_id number, p_qty number, p_price number, p_discount number default 0);
  procedure delete_line(p_line_id number);
  procedure recalc(p_doc_id number);                     -- a draft sale: reprice first
  procedure reprice(p_doc_id number);                    -- the promotions and the discount of the document
  procedure set_doc_discount(p_doc_id number, p_pct number default 0, p_amount number default 0,
                             p_reason varchar2 default null);   -- on the whole document, with a reason
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
  function sell_serials(p_doc_id number, p_item_id number, p_qty number) return number;
                                                                         -- p_qty of the oldest: how many
  procedure release_serial(p_serial_id number);                         -- back from a draft sale
  function reveal_pin(p_serial_id number, p_user varchar2 default null) return varchar2;
  function receipt_pin(p_serial_id number) return varchar2;             -- a card sold today

  -- baskets and sets (kits): what one has (p_qty 0: out), made before (assemble_kit; a negative
  -- quantity takes them apart), or sold before they are made (post_doc: the ready ones first)
  procedure set_component(p_kit_id number, p_component_id number, p_qty number);
  procedure assemble_kit(p_kit_id number, p_qty number, p_note varchar2 default null);
  function kit_cost(p_kit_id number) return number;

  -- promotions: PCT (% off), NM (buy N get M free), BUNDLE (items together for a price); their items
  -- or categories (promo_item: p_qty 0 out; a bundle: items only, with the quantity each)
  function new_promo(p_name varchar2, p_kind varchar2, p_from date, p_to date, p_pct number default null,
                     p_buy number default null, p_free number default null,
                     p_price number default null) return number;
  procedure promo_item(p_promo_id number, p_item_id number default null, p_category_id number default null,
                       p_qty number default 1);
  procedure promo_active(p_promo_id number, p_active varchar2);         -- 'Y' or 'N'

  -- clothes and shoes: a variant of a model (a colour and/or a size), an item of its own; the first one
  -- makes the item a model (not sold, no stock); model_price: the price to the model and its variants
  function make_variant(p_model_id number, p_color_id number default null, p_size_id number default null,
                        p_barcode varchar2 default null) return number;
  procedure model_price(p_model_id number, p_price number);

  -- receipts from customers and payments to suppliers (what settles the invoices on credit): CASH,
  -- CARD or BANK; with a register (CASH, CARD): a move of its open Z too
  function receive(p_customer_id number, p_amount number, p_method varchar2 default 'CASH',
                   p_date date default trunc(sysdate), p_register_id number default null,
                   p_notes varchar2 default null) return number;
  function pay(p_supplier_id number, p_amount number, p_method varchar2 default 'BANK',
               p_date date default trunc(sysdate), p_register_id number default null,
               p_notes varchar2 default null) return number;
  procedure cancel_payment(p_payment_id number);

  -- reservations (e.g. New Year cakes): a name, a phone, the day of the pickup; their quantities are
  -- reserved (MM_ITEM_AVAIL) until the delivery, a receipt that counts the deposit
  function new_reservation(p_name varchar2, p_phone varchar2, p_pickup_date date,
                           p_customer_id number default null, p_notes varchar2 default null) return number;
  procedure reserve(p_res_id number, p_item_id number, p_qty number, p_price number default null);  -- 0: out
  procedure take_deposit(p_res_id number, p_register_id number, p_amount number,
                         p_payment varchar2 default 'CASH');
  function deliver(p_res_id number, p_register_id number, p_payment varchar2 default 'CASH') return number;
  procedure cancel_reservation(p_res_id number, p_register_id number default null,
                               p_refund varchar2 default 'Y');

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

  -- a model is not sold, counted, reserved or put in a basket: its variants are
  procedure not_model(p_item_id number) is
    m varchar2(1);
    c varchar2(20);
  begin
    select is_model, code into m, c from mm_item where id = p_item_id;
    if m = 'Y' then
      fail(61, 'Το ' || c || ' είναι μοντέλο: διάλεξε χρώμα και μέγεθος');
    end if;
  exception
    when no_data_found then null;
  end;

  -- a retail receipt: at most MAX_PER_SALE of an item (p_extra: what is about to be added); an
  -- invoice of sale has no limit (a reseller takes 50 cards: 50 serials on one line)
  procedure check_max(p_doc_id number, p_item_id number, p_extra number) is
    m number;
    c varchar2(20);
    q number;
    n number;
  begin
    select count(*) into n from mm_doc d where d.id = p_doc_id and d.doc_type = 'ALP';
    if n = 0 then
      return;
    end if;
    select max_per_sale, code into m, c from mm_item where id = p_item_id;
    if m is null then
      return;
    end if;
    select nvl(sum(qty), 0) into q from mm_doc_line where doc_id = p_doc_id and item_id = p_item_id;
    if q + p_extra > m then
      fail(57, 'Το ' || c || ' πουλιέται το πολύ ' || m || ' ανά απόδειξη λιανικής');
    end if;
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
    elsif i.wholesale_price is not null then
      return i.wholesale_price;
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

  -- the promotions of the day of a draft sale on its lines, then the discount of the document spread
  -- over them (by value: the VAT of each rate stays right); every line once more: net, VAT, total
  procedure reprice(p_doc_id number) is
    type t_line is record (id number, item_id number, parent_id number, cat_id number, qty number, base number,
                           rate number, pdisc number, ddisc number, promo number, used boolean);
    type t_lines is table of t_line index by pls_integer;
    l t_lines;
    n pls_integer := 0;
    d mm_doc%rowtype;
    t mm_doc_type%rowtype;

    function in_promo(i pls_integer, p_promo number) return boolean is
      c number;
    begin
      select count(*) into c from mm_promo_item
      where promo_id = p_promo and (item_id in (l(i).item_id, l(i).parent_id) or category_id = l(i).cat_id);
      return c > 0;
    end;
  begin
    select * into d from mm_doc where id = p_doc_id;
    t := doc_type_row(d.doc_type);
    if not (d.status = 'D' and t.side = 'S' and t.stock_sign = -1) then
      return;
    end if;
    for x in (select dl.id, dl.item_id, i.parent_id, i.category_id, dl.qty, dl.price, dl.discount, dl.vat_rate
              from mm_doc_line dl join mm_item i on i.id = dl.item_id
              where dl.doc_id = p_doc_id order by dl.line_no) loop
      n := n + 1;
      l(n).id := x.id; l(n).item_id := x.item_id; l(n).parent_id := x.parent_id;
      l(n).cat_id := x.category_id; l(n).qty := x.qty;
      l(n).base := round(x.price * x.qty * (1 - x.discount / 100), 2);
      l(n).rate := x.vat_rate; l(n).pdisc := 0; l(n).ddisc := 0; l(n).promo := null; l(n).used := false;
    end loop;

    -- the promotions are of the till: a retail receipt only (an invoice of sale has its wholesale
    -- price); the discount of the document (step 4) is for every sale
    -- 1. bundles: as many times as all their items are there
    for p in (select * from mm_promo where kind = 'BUNDLE' and active = 'Y' and d.doc_type = 'ALP'
              and d.doc_date between date_from and date_to order by id) loop
      declare
        type t_num is table of number index by pls_integer;
        first_line t_num;     -- by component: the line that takes its part
        part t_num;           -- by component: its value in one bundle
        times number;
        value_ number := 0;
        k pls_integer := 0;
        ok boolean := true;
        q number;
        f pls_integer;
        disc number;
        given number := 0;
      begin
        for c in (select item_id, qty from mm_promo_item where promo_id = p.id and item_id is not null order by id) loop
          k := k + 1;
          q := 0; f := null;
          for i in 1 .. n loop
            if not l(i).used and l(i).item_id = c.item_id and l(i).qty > 0 then
              q := q + l(i).qty;
              f := nvl(f, i);
            end if;
          end loop;
          if f is null then
            ok := false;
            exit;
          end if;
          times := least(nvl(times, q), floor(q / c.qty));
          first_line(k) := f;
          part(k) := c.qty * l(f).base / l(f).qty;
          value_ := value_ + part(k);
        end loop;
        if ok and k > 0 and times >= 1 and value_ > p.bundle_price then
          disc := round(times * (value_ - p.bundle_price), 2);
          for j in 1 .. k loop
            declare
              x number := case when j = k then disc - given else round(disc * part(j) / value_, 2) end;
            begin
              l(first_line(j)).pdisc := l(first_line(j)).pdisc + x;
              l(first_line(j)).promo := p.id;
              given := given + x;
            end;
          end loop;
          for i in 1 .. n loop          -- the lines of its items: no other promotion
            for c in (select 1 from mm_promo_item where promo_id = p.id and item_id = l(i).item_id) loop
              l(i).used := true;
              l(i).promo := p.id;
            end loop;
          end loop;
        end if;
      end;
    end loop;

    -- 2. buy N get M free: the cheapest pieces of the pool free
    for p in (select * from mm_promo where kind = 'NM' and active = 'Y' and d.doc_type = 'ALP'
              and d.doc_date between date_from and date_to order by id) loop
      declare
        units number := 0;
        free_ number;
        best pls_integer;
        taken boolean;
        type t_flag is table of boolean index by pls_integer;
        done t_flag;
        take number;
      begin
        for i in 1 .. n loop
          if not l(i).used and in_promo(i, p.id) then
            units := units + floor(l(i).qty);
          end if;
        end loop;
        free_ := floor(units / (p.buy_qty + p.free_qty)) * p.free_qty;
        if free_ > 0 then
          loop
            exit when free_ = 0;
            best := null;
            for i in 1 .. n loop
              if not l(i).used and not done.exists(i) and floor(l(i).qty) > 0 and in_promo(i, p.id) then
                if best is null or l(i).base / l(i).qty < l(best).base / l(best).qty then
                  best := i;
                end if;
              end if;
            end loop;
            exit when best is null;
            take := least(free_, floor(l(best).qty));
            l(best).pdisc := l(best).pdisc + round(take * l(best).base / l(best).qty, 2);
            l(best).promo := p.id;
            free_ := free_ - take;
            done(best) := true;
          end loop;
          for i in 1 .. n loop
            if not l(i).used and in_promo(i, p.id) then
              l(i).used := true;
            end if;
          end loop;
        end if;
      end;
    end loop;

    -- 3. % off: the best one for each line still free
    for i in 1 .. n loop
      if not l(i).used then
        for p in (select pr.id, pr.pct from mm_promo pr
                  where pr.kind = 'PCT' and pr.active = 'Y' and d.doc_type = 'ALP'
                    and d.doc_date between pr.date_from and pr.date_to
                    and exists (select 1 from mm_promo_item x where x.promo_id = pr.id
                                and (x.item_id in (l(i).item_id, l(i).parent_id) or x.category_id = l(i).cat_id))
                  order by pr.pct desc, pr.id fetch first 1 row only) loop
          l(i).pdisc := round(l(i).base * p.pct / 100, 2);
          l(i).promo := p.id;
        end loop;
      end if;
    end loop;

    -- 4. the discount of the document, spread by the value of each line after its promotion
    declare
      tot number := 0;
      dd number;
      given number := 0;
      big pls_integer;
    begin
      for i in 1 .. n loop
        tot := tot + (l(i).base - l(i).pdisc);
        if big is null or l(i).base - l(i).pdisc > l(big).base - l(big).pdisc then
          big := i;
        end if;
      end loop;
      dd := least(tot, d.disc_amount + round(tot * d.disc_pct / 100, 2));
      if dd > 0 and tot > 0 then
        for i in 1 .. n loop
          l(i).ddisc := round(dd * (l(i).base - l(i).pdisc) / tot, 2);
          given := given + l(i).ddisc;
        end loop;
        l(big).ddisc := l(big).ddisc + (dd - given);
      end if;
    end;

    -- 5. the lines again
    for i in 1 .. n loop
      declare
        g number := greatest(l(i).base - l(i).pdisc - l(i).ddisc, 0);
        ne number; va number; tt number;
      begin
        if t.prices_incl_vat = 'Y' then
          tt := g; ne := round(g / (1 + l(i).rate / 100), 2); va := tt - ne;
        else
          ne := g; va := round(g * l(i).rate / 100, 2); tt := ne + va;
        end if;
        update mm_doc_line
        set promo_id = case when l(i).pdisc > 0 then l(i).promo end,
            promo_disc = l(i).pdisc, doc_disc = l(i).ddisc, net = ne, vat = va, total = tt
        where id = l(i).id;
      end;
    end loop;
  end;

  procedure recalc(p_doc_id number) is
  begin
    reprice(p_doc_id);
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
    not_model(p_item_id);
    check_max(p_doc_id, p_item_id, p_qty);
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
    check_max(l.doc_id, l.item_id, p_qty - l.qty);
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
    update mm_reservation set doc_id = null where doc_id = p_doc_id;   -- its delivery again later
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
    for x in (select distinct item_id from mm_doc_line where doc_id = p_doc_id) loop
      check_max(p_doc_id, x.item_id, 0);
    end loop;
    -- a line of cards: as many serials as its quantity
    for l in (select l.id, l.qty, i.code from mm_doc_line l join mm_item i on i.id = l.item_id
              where l.doc_id = p_doc_id and i.serial_tracked = 'Y') loop
      select count(*) into lines from mm_serial where in_line_id = l.id or out_line_id = l.id;
      if lines <> l.qty then
        fail(28, 'Το ' || l.code || ': ' || l.qty || ' τεμάχια, ' || lines || ' serials');
      end if;
    end loop;
    recalc(p_doc_id);
    select total into d.total from mm_doc where id = p_doc_id;
    if d.deposit > d.total then
      fail(47, 'Η προκαταβολή (' || d.deposit || ') είναι πάνω από το σύνολο (' || d.total || ')');
    end if;
    no_ := t.next_no;
    update mm_doc_type set next_no = next_no + 1 where code = t.code;
    update mm_doc set doc_no = no_, status = 'P', z_id = z where id = p_doc_id
    returning total into d.total;

    for l in (select l.*, i.kit from mm_doc_line l join mm_item i on i.id = l.item_id
              where l.doc_id = p_doc_id) loop
      if l.kit = 'Y' and t.stock_sign = -1 then
        -- a kit out: the ready ones first, the rest from its components
        declare
          ready number;
          take number;
        begin
          select greatest(stock, 0) into ready from mm_item where id = l.item_id;
          take := least(ready, l.qty);
          stock_move(l.item_id, 'DOC', -take, p_doc_id, l.id);
          for c in (select component_id, qty from mm_kit_component where kit_id = l.item_id) loop
            stock_move(c.component_id, 'DOC', -(l.qty - take) * c.qty, p_doc_id, l.id);
          end loop;
        end;
      else
        stock_move(l.item_id, 'DOC', t.stock_sign * l.qty, p_doc_id, l.id);
      end if;
      if t.side = 'P' and t.stock_sign = 1 and l.qty > 0 then
        update mm_item set cost = round(l.net / l.qty, 4) where id = l.item_id;   -- the last cost
      end if;
    end loop;
    update mm_serial set status = 'A' where in_doc_id = p_doc_id and status = 'N';
    update mm_serial set status = 'S', sold_at = sysdate where out_doc_id = p_doc_id and status = 'R';

    -- the money of now: the total less a deposit paid before (a reservation)
    if z is not null and d.payment in ('CASH', 'CARD') and d.total - d.deposit <> 0 then
      insert into mm_cash_move (register_id, z_id, kind, payment, amount, doc_id)
      values (d.register_id, z, case when t.stock_sign > 0 then 'REFUND' else 'SALE' end, d.payment,
              case when t.stock_sign > 0 then -(d.total - d.deposit) else d.total - d.deposit end, p_doc_id);
    end if;
    update mm_reservation set status = 'D' where doc_id = p_doc_id;
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
    -- back exactly what went (a kit: its ready ones and its components)
    for m in (select item_id, doc_line_id, sum(qty) qty from mm_stock_move
              where doc_id = p_doc_id and kind = 'DOC'
              group by item_id, doc_line_id) loop
      stock_move(m.item_id, 'DOC', -m.qty, p_doc_id, m.doc_line_id, 'Ακύρωση');
    end loop;
    update mm_serial set status = 'X' where in_doc_id = p_doc_id;
    update mm_serial set status = 'A', sold_at = null, out_line_id = null, out_doc_id = null
    where out_doc_id = p_doc_id and status = 'S';
    insert into mm_cash_move (register_id, z_id, kind, payment, amount, doc_id, note)
    select register_id, z_id, case kind when 'SALE' then 'REFUND' else 'SALE' end, payment, -amount, doc_id, 'Ακύρωση'
    from mm_cash_move where doc_id = p_doc_id and kind in ('SALE', 'REFUND');
    update mm_reservation set status = 'O', doc_id = null where doc_id = p_doc_id;
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
    not_model(p_item_id);
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
        -- the money of the sales and of the deposits, as it came in (a deposit on its day)
        (cash, card, deposits) =
          (select nvl(sum(case when payment = 'CASH' then amount end), 0),
                  nvl(sum(case when payment = 'CARD' then amount end), 0),
                  nvl(sum(case when kind = 'DEPOSIT' then amount end), 0)
           from mm_cash_move where z_id = m.id and kind in ('SALE', 'REFUND', 'DEPOSIT')),
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
    check_max(p_doc_id, it, 1);
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

  -- many cards at once (an invoice to a reseller): the p_qty oldest available, all or none
  function sell_serials(p_doc_id number, p_item_id number, p_qty number) return number is
    sid number;
  begin
    if nvl(p_qty, 0) < 1 or p_qty <> trunc(p_qty) then
      fail(24, 'Λάθος ποσότητα');
    end if;
    savepoint mm_sell_serials;
    for k in 1 .. p_qty loop
      sid := sell_serial(p_doc_id, p_item_id);
    end loop;
    return p_qty;
  exception
    when others then
      rollback to mm_sell_serials;
      raise;
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
  function make_variant(p_model_id number, p_color_id number default null, p_size_id number default null,
                        p_barcode varchar2 default null) return number is
    m mm_item%rowtype;
    cc varchar2(10); cn varchar2(40);
    sc varchar2(10);
    n number;
    v number;
  begin
    begin
      select * into m from mm_item where id = p_model_id;
    exception
      when no_data_found then fail(6, 'Δεν υπάρχει είδος ' || p_model_id);
    end;
    if m.parent_id is not null then
      fail(63, 'Το ' || m.code || ' είναι ήδη παραλλαγή: δεν γίνεται μοντέλο');
    end if;
    if m.serial_tracked = 'Y' or m.kit = 'Y' then
      fail(63, 'Το ' || m.code || ' έχει serials ή είναι καλάθι: δεν γίνεται μοντέλο');
    end if;
    if p_color_id is null and p_size_id is null then
      fail(64, 'Η παραλλαγή θέλει χρώμα ή μέγεθος');
    end if;
    if m.is_model = 'N' then
      -- an item becomes a model only while nothing has happened to it
      select count(*) into n from mm_stock_move where item_id = p_model_id;
      select n + count(*) into n from mm_doc_line where item_id = p_model_id;
      select n + count(*) into n from mm_kit_component where component_id = p_model_id;
      if n > 0 then
        fail(62, 'Το ' || m.code || ' έχει ήδη κινήσεις: φτιάξε νέο μοντέλο');
      end if;
      update mm_item set is_model = 'Y', barcode = null where id = p_model_id;
    end if;
    if p_color_id is not null then
      begin
        select code, name into cc, cn from mm_color where id = p_color_id;
      exception
        when no_data_found then fail(64, 'Δεν υπάρχει χρώμα ' || p_color_id);
      end;
    end if;
    if p_size_id is not null then
      begin
        select code into sc from mm_size where id = p_size_id;
      exception
        when no_data_found then fail(64, 'Δεν υπάρχει μέγεθος ' || p_size_id);
      end;
    end if;
    insert into mm_item (code, barcode, name, category_id, vat_code, unit, price, wholesale_price, cost, min_stock,
                         max_per_sale, parent_id, color_id, size_id, active)
    values (substr(m.code || case when cc is not null then '-' || cc end || case when sc is not null then '-' || sc end, 1, 20),
            p_barcode,
            substr(m.name || case when cn is not null then ' ' || cn end || case when sc is not null then ' ' || sc end, 1, 100),
            m.category_id, m.vat_code, m.unit, m.price, m.wholesale_price, m.cost, 0, m.max_per_sale,
            p_model_id, p_color_id, p_size_id, m.active)
    returning id into v;
    return v;
  exception
    when dup_val_on_index then fail(65, 'Η παραλλαγή (ή ο κωδικός/barcode της) υπάρχει ήδη');
  end;

  procedure model_price(p_model_id number, p_price number) is
    n number;
  begin
    if p_price is null or p_price < 0 then
      fail(24, 'Λάθος τιμή');
    end if;
    select count(*) into n from mm_item where id = p_model_id and is_model = 'Y';
    if n = 0 then
      fail(66, 'Το είδος ' || p_model_id || ' δεν είναι μοντέλο');
    end if;
    update mm_item set price = p_price where id = p_model_id or parent_id = p_model_id;
    -- (the wholesale price of the variants: as each one has it)
  end;

  -- ---------------------------------------------------------------------------------------------
  procedure set_doc_discount(p_doc_id number, p_pct number default 0, p_amount number default 0,
                             p_reason varchar2 default null) is
    d mm_doc%rowtype := draft(p_doc_id);
    t mm_doc_type%rowtype := doc_type_row(d.doc_type);
  begin
    if not (t.side = 'S' and t.stock_sign = -1) then
      fail(59, 'Έκπτωση στο σύνολο γίνεται μόνο σε πώληση');
    end if;
    if nvl(p_pct, 0) < 0 or nvl(p_pct, 0) > 100 or nvl(p_amount, 0) < 0 then
      fail(59, 'Λάθος έκπτωση: 0 έως 100% ή θετικό ποσό');
    end if;
    if (nvl(p_pct, 0) > 0 or nvl(p_amount, 0) > 0) and trim(p_reason) is null then
      fail(59, 'Η έκπτωση στο σύνολο θέλει αιτιολογία');
    end if;
    update mm_doc set disc_pct = nvl(p_pct, 0), disc_amount = nvl(p_amount, 0), disc_reason = trim(p_reason)
    where id = p_doc_id;
    recalc(p_doc_id);
  end;

  function new_promo(p_name varchar2, p_kind varchar2, p_from date, p_to date, p_pct number default null,
                     p_buy number default null, p_free number default null,
                     p_price number default null) return number is
    v number;
  begin
    if trim(p_name) is null or p_from is null or p_to is null or p_to < p_from then
      fail(58, 'Η προσφορά θέλει όνομα και διάστημα ημερομηνιών');
    end if;
    -- (nvl: a NULL would make the test unknown, and the IF would let it pass)
    if not ((p_kind = 'PCT' and nvl(p_pct, 0) > 0 and nvl(p_pct, 0) <= 100) or
            (p_kind = 'NM' and nvl(p_buy, 0) >= 1 and nvl(p_free, 0) >= 1) or
            (p_kind = 'BUNDLE' and nvl(p_price, -1) >= 0)) then
      fail(58, 'Λάθος προσφορά: PCT με 0-100%, NM με N και M, BUNDLE με τιμή');
    end if;
    insert into mm_promo (name, kind, date_from, date_to, pct, buy_qty, free_qty, bundle_price)
    values (trim(p_name), p_kind, trunc(p_from), trunc(p_to),
            case when p_kind = 'PCT' then p_pct end,
            case when p_kind = 'NM' then p_buy end, case when p_kind = 'NM' then p_free end,
            case when p_kind = 'BUNDLE' then p_price end)
    returning id into v;
    return v;
  exception
    when dup_val_on_index then fail(58, 'Υπάρχει ήδη προσφορά με όνομα ' || p_name);
  end;

  procedure promo_active(p_promo_id number, p_active varchar2) is
  begin
    if p_active not in ('Y', 'N') then
      fail(58, 'Ενεργή: Y ή N');
    end if;
    update mm_promo set active = p_active where id = p_promo_id;
    if sql%rowcount = 0 then
      fail(58, 'Δεν υπάρχει προσφορά ' || p_promo_id);
    end if;
  end;

  procedure promo_item(p_promo_id number, p_item_id number default null, p_category_id number default null,
                       p_qty number default 1) is
    k varchar2(6);
  begin
    begin
      select kind into k from mm_promo where id = p_promo_id;
    exception
      when no_data_found then fail(58, 'Δεν υπάρχει προσφορά ' || p_promo_id);
    end;
    if (p_item_id is null) = (p_category_id is null) then
      fail(60, 'Η προσφορά αφορά είδος ή κατηγορία (ένα από τα δύο)');
    end if;
    if k = 'BUNDLE' and p_item_id is null then
      fail(60, 'Ένα πακέτο σε τιμή έχει είδη, όχι κατηγορίες');
    end if;
    delete from mm_promo_item
    where promo_id = p_promo_id and (item_id = p_item_id or category_id = p_category_id);
    if nvl(p_qty, 0) > 0 then
      insert into mm_promo_item (promo_id, item_id, category_id, qty)
      values (p_promo_id, p_item_id, p_category_id, p_qty);
    end if;
  end;

  -- ---------------------------------------------------------------------------------------------
  function kit_cost(p_kit_id number) return number is
    v number;
  begin
    select nvl(sum(kc.qty * c.cost), 0) into v
    from mm_kit_component kc join mm_item c on c.id = kc.component_id
    where kc.kit_id = p_kit_id;
    return round(v, 4);
  end;

  procedure set_component(p_kit_id number, p_component_id number, p_qty number) is
    k mm_item%rowtype;
    c mm_item%rowtype;
    n number;
  begin
    begin
      select * into k from mm_item where id = p_kit_id;
      select * into c from mm_item where id = p_component_id;
    exception
      when no_data_found then fail(6, 'Δεν υπάρχει είδος');
    end;
    if p_qty is null or p_qty < 0 then
      fail(24, 'Λάθος ποσότητα');
    end if;
    if p_qty = 0 then
      delete from mm_kit_component where kit_id = p_kit_id and component_id = p_component_id;
      select count(*) into n from mm_kit_component where kit_id = p_kit_id;
      if n = 0 then
        update mm_item set kit = 'N' where id = p_kit_id;
      end if;
      return;
    end if;
    if k.serial_tracked = 'Y' or c.serial_tracked = 'Y' then
      fail(53, 'Καλάθι και είδη με serials δεν συνδυάζονται');
    end if;
    not_model(p_kit_id);
    not_model(p_component_id);
    if p_kit_id = p_component_id then
      fail(55, 'Το καλάθι δεν μπαίνει στον εαυτό του');
    end if;
    if c.kit = 'Y' then
      fail(54, 'Το ' || c.code || ' είναι καλάθι: ένα καλάθι δεν μπαίνει σε άλλο');
    end if;
    select count(*) into n from mm_kit_component where component_id = p_kit_id;
    if n > 0 then
      fail(54, 'Το ' || k.code || ' είναι μέρος άλλου καλαθιού: δεν γίνεται καλάθι');
    end if;
    merge into mm_kit_component x
    using (select p_kit_id kit_id, p_component_id component_id from dual) s
    on (x.kit_id = s.kit_id and x.component_id = s.component_id)
    when matched then update set qty = p_qty
    when not matched then insert (kit_id, component_id, qty) values (p_kit_id, p_component_id, p_qty);
    update mm_item set kit = 'Y' where id = p_kit_id and kit = 'N';
  end;

  procedure assemble_kit(p_kit_id number, p_qty number, p_note varchar2 default null) is
    n number;
    note varchar2(200) := nvl(p_note, case when p_qty > 0 then 'Συναρμολόγηση' else 'Αποσυναρμολόγηση' end);
  begin
    select count(*) into n from mm_kit_component where kit_id = p_kit_id;
    if n = 0 then
      fail(56, 'Το είδος ' || p_kit_id || ' δεν είναι καλάθι (δεν έχει σύνθεση)');
    end if;
    if nvl(p_qty, 0) = 0 then
      fail(24, 'Λάθος ποσότητα');
    end if;
    for c in (select component_id, qty from mm_kit_component where kit_id = p_kit_id) loop
      stock_move(c.component_id, 'ASM', -p_qty * c.qty, p_note => note);
    end loop;
    stock_move(p_kit_id, 'ASM', p_qty, p_note => note);
    if p_qty > 0 then
      n := kit_cost(p_kit_id);     -- first: a function on MM_ITEM inside its own UPDATE is ORA-04091
      update mm_item set cost = n where id = p_kit_id;
    end if;
  end;

  -- ---------------------------------------------------------------------------------------------
  function new_payment(p_kind varchar2, p_customer_id number, p_supplier_id number, p_amount number,
                       p_method varchar2, p_date date, p_register_id number, p_notes varchar2) return number is
    v number;
    z number;
  begin
    if nvl(p_amount, 0) <= 0 then
      fail(67, 'Το ποσό πρέπει να είναι θετικό');
    end if;
    if p_method not in ('CASH', 'CARD', 'BANK') then
      fail(68, 'Τρόπος: μετρητά, κάρτα ή έμβασμα');
    end if;
    if p_kind = 'R' and p_customer_id is null or p_kind = 'P' and p_supplier_id is null then
      fail(69, case p_kind when 'R' then 'Η είσπραξη θέλει πελάτη' else 'Η πληρωμή θέλει προμηθευτή' end);
    end if;
    if p_register_id is not null and p_method <> 'BANK' then
      z := open_z_of(p_register_id);
      if z is null then
        fail(12, 'Το ταμείο δεν έχει ανοιχτό Ζ');
      end if;
    end if;
    insert into mm_payment (kind, customer_id, supplier_id, pay_date, amount, method, register_id, notes)
    values (p_kind, p_customer_id, p_supplier_id, nvl(trunc(p_date), trunc(sysdate)), p_amount, p_method,
            case when z is not null then p_register_id end, p_notes)
    returning id into v;
    if z is not null then
      insert into mm_cash_move (register_id, z_id, kind, payment, amount, payment_id, note)
      values (p_register_id, z, case p_kind when 'R' then 'IN' else 'OUT' end, p_method,
              case p_kind when 'R' then p_amount else -p_amount end, v,
              case p_kind when 'R' then 'Είσπραξη ' else 'Πληρωμή ' end || v);
    end if;
    return v;
  end;

  function receive(p_customer_id number, p_amount number, p_method varchar2 default 'CASH',
                   p_date date default trunc(sysdate), p_register_id number default null,
                   p_notes varchar2 default null) return number is
  begin
    return new_payment('R', p_customer_id, null, p_amount, p_method, p_date, p_register_id, p_notes);
  end;

  function pay(p_supplier_id number, p_amount number, p_method varchar2 default 'BANK',
               p_date date default trunc(sysdate), p_register_id number default null,
               p_notes varchar2 default null) return number is
  begin
    return new_payment('P', null, p_supplier_id, p_amount, p_method, p_date, p_register_id, p_notes);
  end;

  -- cancelled: its move of the register back, while that Z is open
  procedure cancel_payment(p_payment_id number) is
    p mm_payment%rowtype;
    zs varchar2(1);
  begin
    begin
      select * into p from mm_payment where id = p_payment_id for update;
    exception
      when no_data_found then fail(70, 'Δεν υπάρχει είσπραξη/πληρωμή ' || p_payment_id);
    end;
    if p.status <> 'P' then
      fail(70, 'Η είσπραξη/πληρωμή έχει ήδη ακυρωθεί');
    end if;
    for m in (select * from mm_cash_move where payment_id = p_payment_id) loop
      select status into zs from mm_z where id = m.z_id;
      if zs = 'C' then
        fail(14, 'Το Ζ της έχει κλείσει: κάνε αντίστροφη κίνηση');
      end if;
      insert into mm_cash_move (register_id, z_id, kind, payment, amount, payment_id, note)
      values (m.register_id, m.z_id, case m.kind when 'IN' then 'OUT' else 'IN' end, m.payment, -m.amount,
              p_payment_id, 'Ακύρωση');
    end loop;
    update mm_payment set status = 'C' where id = p_payment_id;
  end;

  -- ---------------------------------------------------------------------------------------------
  -- the reservation locked, for a change: open, and no receipt of its delivery waiting
  function open_res(p_res_id number) return mm_reservation%rowtype is
    r mm_reservation%rowtype;
  begin
    select * into r from mm_reservation where id = p_res_id for update;
    if r.status <> 'O' or r.doc_id is not null then
      fail(46, 'Η κράτηση ' || p_res_id || ' δεν είναι ανοιχτή' ||
               case when r.doc_id is not null then ' (έχει απόδειξη παράδοσης)' end);
    end if;
    return r;
  exception
    when no_data_found then fail(50, 'Δεν υπάρχει κράτηση ' || p_res_id);
  end;

  function new_reservation(p_name varchar2, p_phone varchar2, p_pickup_date date,
                           p_customer_id number default null, p_notes varchar2 default null) return number is
    v number;
  begin
    if trim(p_name) is null or p_phone is null or not regexp_like(p_phone, '^[0-9+ ]{5,20}$') then
      fail(45, 'Η κράτηση θέλει όνομα και τηλέφωνο');
    end if;
    if p_pickup_date is null or trunc(p_pickup_date) < trunc(sysdate) then
      fail(49, 'Η ημερομηνία παραλαβής δεν μπορεί να είναι στο παρελθόν');
    end if;
    insert into mm_reservation (name, phone, customer_id, pickup_date, notes)
    values (trim(p_name), p_phone, p_customer_id, trunc(p_pickup_date), p_notes)
    returning id into v;
    return v;
  end;

  procedure reserve(p_res_id number, p_item_id number, p_qty number, p_price number default null) is
    r mm_reservation%rowtype := open_res(p_res_id);
    i mm_item%rowtype;
  begin
    begin
      select * into i from mm_item where id = p_item_id;
    exception
      when no_data_found then fail(6, 'Δεν υπάρχει είδος ' || p_item_id);
    end;
    if i.active = 'N' then
      fail(7, 'Το είδος ' || i.code || ' δεν είναι ενεργό');
    end if;
    if i.serial_tracked = 'Y' then
      fail(52, 'Τα είδη με serials δεν μπαίνουν σε κράτηση');
    end if;
    not_model(p_item_id);
    if p_qty is null or p_qty < 0 then
      fail(24, 'Λάθος ποσότητα');
    end if;
    if p_qty = 0 then
      delete from mm_reservation_line where reservation_id = p_res_id and item_id = p_item_id;
    else
      merge into mm_reservation_line l
      using (select p_res_id reservation_id, p_item_id item_id from dual) s
      on (l.reservation_id = s.reservation_id and l.item_id = s.item_id)
      when matched then update set qty = p_qty, price = nvl(p_price, l.price)
      when not matched then insert (reservation_id, item_id, qty, price)
        values (p_res_id, p_item_id, p_qty, nvl(p_price, i.price));
    end if;
  end;

  procedure take_deposit(p_res_id number, p_register_id number, p_amount number,
                         p_payment varchar2 default 'CASH') is
    r mm_reservation%rowtype := open_res(p_res_id);
    z number := open_z_of(p_register_id);
  begin
    if z is null then
      fail(12, 'Το ταμείο δεν έχει ανοιχτό Ζ');
    end if;
    if nvl(p_amount, 0) <= 0 or p_payment not in ('CASH', 'CARD') then
      fail(48, 'Η προκαταβολή θέλει θετικό ποσό, με μετρητά ή κάρτα');
    end if;
    insert into mm_cash_move (register_id, z_id, kind, payment, amount, reservation_id, note)
    values (p_register_id, z, 'DEPOSIT', p_payment, p_amount, p_res_id, 'Κράτηση ' || p_res_id);
    update mm_reservation set deposit = deposit + p_amount where id = p_res_id;
  end;

  -- the receipt of the delivery: a draft on the register, the lines at the prices of the
  -- reservation, the deposit on it (post_doc takes only the rest); post_doc makes it delivered
  function deliver(p_res_id number, p_register_id number, p_payment varchar2 default 'CASH') return number is
    r mm_reservation%rowtype := open_res(p_res_id);
    d number;
    l number;
    n number;
  begin
    select count(*) into n from mm_reservation_line where reservation_id = p_res_id;
    if n = 0 then
      fail(51, 'Η κράτηση δεν έχει είδη');
    end if;
    d := new_doc('ALP', r.customer_id, null, p_register_id, p_payment);
    for x in (select * from mm_reservation_line where reservation_id = p_res_id order by id) loop
      l := add_line(d, x.item_id, x.qty, x.price);
    end loop;
    update mm_doc set deposit = r.deposit,
                      notes = 'Κράτηση ' || p_res_id || ': ' || r.name || ', ' || r.phone where id = d;
    update mm_reservation set doc_id = d where id = p_res_id;
    return d;
  end;

  -- cancelled: the deposit back (the same ways it came), or kept (p_refund = 'N')
  procedure cancel_reservation(p_res_id number, p_register_id number default null,
                               p_refund varchar2 default 'Y') is
    r mm_reservation%rowtype := open_res(p_res_id);
    z number;
  begin
    if p_refund = 'Y' and r.deposit > 0 then
      z := open_z_of(p_register_id);
      if z is null then
        fail(12, 'Το ταμείο δεν έχει ανοιχτό Ζ');
      end if;
      insert into mm_cash_move (register_id, z_id, kind, payment, amount, reservation_id, note)
      select p_register_id, z, 'DEPOSIT', payment, -sum(amount), p_res_id, 'Επιστροφή προκαταβολής'
      from mm_cash_move where reservation_id = p_res_id and kind = 'DEPOSIT'
      group by payment having sum(amount) <> 0;
    end if;
    update mm_reservation set status = 'C' where id = p_res_id;
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
    not_model(it);
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

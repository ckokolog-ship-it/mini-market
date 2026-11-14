-- MM_UI.pls -- the package UI of the forms of the mini market (MM_ITEMS, MM_CUSTOMERS,
-- MM_SUPPLIERS, MM_CARDS, MM_RESERVATIONS): mkforms.py puts it in each form. The triggers only call it:
--   WHEN-NEW-FORM-INSTANCE  ui.init
--   WHEN-NEW-RECORD-INSTANCE ui.master(:SYSTEM.TRIGGER_BLOCK)   (a master: its detail again)
--   WHEN-BUTTON-PRESSED     ui.press(:SYSTEM.TRIGGER_ITEM)
--   WHEN-VALIDATE-ITEM      ui.validate(:SYSTEM.TRIGGER_ITEM)
--   POST-QUERY              ui.post_query(:SYSTEM.TRIGGER_BLOCK)
--   ON-ERROR                ui.on_error(ERROR_CODE, ERROR_TYPE, ERROR_TEXT, DBMS_ERROR_TEXT)
-- Items through NAME_IN and COPY (no :BLOCK.ITEM): so tests/test_forms.py compiles and runs it in
-- the database, without the Forms. Every Greek string here becomes mm_text.t('T...') (mkforms.py).
PACKAGE ui IS
  PROCEDURE init;
  PROCEDURE press(p_item VARCHAR2);
  PROCEDURE validate(p_item VARCHAR2);
  PROCEDURE post_query(p_block VARCHAR2);
  PROCEDURE master(p_block VARCHAR2);
  PROCEDURE on_error(p_code NUMBER, p_type VARCHAR2, p_text VARCHAR2, p_dbtext VARCHAR2);
  FUNCTION friendly(p_dbtext VARCHAR2) RETURN VARCHAR2;
END;
-- BODY
PACKAGE BODY ui IS
  c_block CONSTANT VARCHAR2(30) := 'BLOCK'; -- BLOCK
  c_where CONSTANT VARCHAR2(400) := ''; -- WHERE
  c_detail CONSTANT VARCHAR2(30) := ''; -- DETAIL
  g_master NUMBER;                  -- the master whose detail is on the screen

  FUNCTION num(p_item VARCHAR2) RETURN NUMBER IS
  BEGIN
    RETURN to_number(name_in(p_item));
  END;

  FUNCTION tx(p_key VARCHAR2) RETURN VARCHAR2 IS
  BEGIN
    RETURN mm_text.t(p_key);
  END;

  PROCEDURE fail(p_msg VARCHAR2) IS
  BEGIN
    message(p_msg);
    RAISE form_trigger_failure;
  END;

  PROCEDURE init IS
  BEGIN
    NULL; -- TEXTS
    go_block(c_block);
    set_block_property(c_block, DEFAULT_WHERE, c_where);
    execute_query;
  END;

  -- the detail of the master record on the screen (once for each master record: going back to the
  -- master brings this trigger again)
  PROCEDURE master(p_block VARCHAR2) IS
    id_ NUMBER := num(p_block || '.ID');
  BEGIN
    IF c_detail IS NULL OR p_block <> c_block OR id_ IS NULL OR id_ = g_master THEN
      RETURN;
    END IF;
    g_master := id_;
    go_block(c_detail);
    execute_query;
    go_block(c_block);
  END;

  PROCEDURE again(p_block VARCHAR2) IS
  BEGIN
    g_master := NULL;
    go_block(p_block);
    execute_query;
    IF p_block <> c_block THEN
      go_block(c_block);
    END IF;
  END;

  -- the register of the box CTL.REG_CODE (T1 by default)
  FUNCTION register_id RETURN NUMBER IS
    c VARCHAR2(10) := upper(nvl(name_in('CTL.REG_CODE'), 'T1'));
    r NUMBER;
  BEGIN
    SELECT id INTO r FROM mm_register WHERE code = c;
    RETURN r;
  EXCEPTION
    WHEN no_data_found THEN
      message('Δεν υπάρχει ταμείο ' || c);
      RAISE form_trigger_failure;
  END;

  -- the buttons of the cards and of the reservations: MM_CORE, then COMMIT (MM_CORE does not commit)
  PROCEDURE action(p_item VARCHAR2) IS
    v NUMBER;
    n NUMBER;
    s NUMBER;
    pin VARCHAR2(40);
  BEGIN
    IF p_item = 'CTL.LOAD' THEN
      v := num('CARD.ID');
      n := mm_core.load_serial(v, name_in('CTL.NEW_SERIAL'), name_in('CTL.NEW_PIN'));
      forms_ddl('COMMIT');
      copy('', 'CTL.NEW_SERIAL');
      copy('', 'CTL.NEW_PIN');
      SELECT stock INTO s FROM mm_item WHERE id = v;
      copy(to_char(s), 'CARD.STOCK');
      again('SER');
      message('Η κάρτα φορτώθηκε');
    ELSIF p_item = 'CTL.PIN' THEN
      pin := mm_core.reveal_pin(num('SER.ID'), name_in('CTL.USERNAME'));
      forms_ddl('COMMIT');                                     -- the log of who saw it
      copy(pin, 'SER.PIN_SHOW');
    ELSIF p_item = 'CTL.NEWRES' THEN
      v := mm_core.new_reservation(name_in('CTL.R_NAME'), name_in('CTL.R_PHONE'),
                                   to_date(name_in('CTL.R_DATE'), 'DD/MM/YYYY'));
      forms_ddl('COMMIT');
      copy('', 'CTL.R_NAME');
      copy('', 'CTL.R_PHONE');
      go_block(c_block);
      set_block_property(c_block, DEFAULT_WHERE, 'id = ' || to_char(v));
      again(c_block);
      message('Νέα κράτηση ' || to_char(v) || ': πρόσθεσε τα είδη της');
    ELSIF p_item = 'CTL.RESERVE' THEN
      mm_core.reserve(num('RES.ID'), num('CTL.ITEM_ID'), nvl(num('CTL.QTY'), 1));
      forms_ddl('COMMIT');
      again('RL');
    ELSIF p_item = 'CTL.DEPOSIT' THEN
      mm_core.take_deposit(num('RES.ID'), register_id, num('CTL.AMOUNT'), upper(nvl(name_in('CTL.PAY'), 'CASH')));
      forms_ddl('COMMIT');
      copy('', 'CTL.AMOUNT');
      again(c_block);
      message('Η προκαταβολή μπήκε στο ταμείο');
    ELSIF p_item = 'CTL.DELIVER' THEN
      v := mm_core.deliver(num('RES.ID'), register_id, upper(nvl(name_in('CTL.PAY'), 'CASH')));
      n := mm_core.post_doc(v);
      forms_ddl('COMMIT');
      again(c_block);
      message('Παραδόθηκε: απόδειξη ' || to_char(n));
    ELSIF p_item = 'CTL.CANCELRES' THEN
      mm_core.cancel_reservation(num('RES.ID'), register_id, 'Y');
      forms_ddl('COMMIT');
      again(c_block);
      message('Η κράτηση ακυρώθηκε');
    END IF;
  EXCEPTION
    WHEN form_trigger_failure THEN
      RAISE;
    WHEN OTHERS THEN
      forms_ddl('ROLLBACK');
      message(friendly(sqlerrm));
  END;

  -- the record chosen in the LOV "find", alone in the block; "all": every record again
  PROCEDURE press(p_item VARCHAR2) IS
    v VARCHAR2(40);
  BEGIN
    IF p_item = 'CTL.FIND' THEN
      copy('', 'CTL.FIND_ID');
      IF show_lov('LOV_FIND') THEN
        v := name_in('CTL.FIND_ID');
        IF v IS NOT NULL THEN
          go_block(c_block);
          set_block_property(c_block, DEFAULT_WHERE, 'id = ' || to_char(to_number(v)));
          g_master := NULL;
          execute_query;
          set_block_property(c_block, DEFAULT_WHERE, c_where);
        END IF;
      END IF;
    ELSIF p_item = 'CTL.ALL' THEN
      copy('', 'CTL.FIND_TEXT');
      go_block(c_block);
      set_block_property(c_block, DEFAULT_WHERE, c_where);
      g_master := NULL;
      execute_query;
    ELSE
      action(p_item);
    END IF;
  END;

  PROCEDURE validate(p_item VARCHAR2) IS
    v VARCHAR2(400) := name_in(p_item);
  BEGIN
    IF v IS NULL THEN
      RETURN;
    END IF;
    IF p_item = 'ITEM.BARCODE' THEN
      IF mm_core.ean_ok(v) = 'N' THEN
        fail('Το barcode δεν είναι σωστό: 8, 12, 13 ή 14 ψηφία, με σωστό ψηφίο ελέγχου');
      END IF;
    ELSIF p_item IN ('ITEM.PRICE', 'ITEM.COST', 'ITEM.MIN_STOCK') THEN
      IF to_number(v) < 0 THEN
        fail('Δεν επιτρέπεται αρνητικός αριθμός');
      END IF;
    ELSIF p_item = 'PARTNER.AFM' THEN
      IF mm_core.afm_ok(v) = 'N' THEN
        fail('Το ΑΦΜ δεν είναι σωστό: 9 ψηφία, με σωστό ψηφίο ελέγχου');
      END IF;
    ELSIF p_item = 'PARTNER.EMAIL' THEN
      IF v NOT LIKE '_%@_%._%' THEN
        fail('Το email δεν είναι σωστό');
      END IF;
    END IF;
  END;

  -- what is not a column of the block: the name of the category, the rate of the VAT, the stock
  -- (MM_ITEM.STOCK is reservable and changes all day: not a database item, so the form never
  -- writes it and never sees "record changed by another user" for it)
  PROCEDURE post_query(p_block VARCHAR2) IS
    n VARCHAR2(200);
    r NUMBER;
    s NUMBER;
    id_ NUMBER;
  BEGIN
    IF p_block = 'ITEM' THEN
      -- NAME_IN outside the SELECT: a built-in of the Forms "may not be used in SQL" (PL/SQL 231)
      id_ := to_number(name_in('ITEM.ID'));
      BEGIN
        SELECT c.name, v.rate, i.stock INTO n, r, s
        FROM mm_item i, mm_category c, mm_vat v
        WHERE i.id = id_ AND c.id = i.category_id AND v.code = i.vat_code;
        copy(n, 'ITEM.CAT_NAME');
        copy(to_char(r), 'ITEM.VAT_RATE');
        copy(to_char(s), 'ITEM.STOCK');
      EXCEPTION
        WHEN no_data_found THEN NULL;
      END;
    ELSIF p_block = 'CARD' THEN
      id_ := num('CARD.ID');
      SELECT stock INTO s FROM mm_item WHERE id = id_;
      copy(to_char(s), 'CARD.STOCK');
    ELSIF p_block = 'RL' THEN
      id_ := num('RL.ITEM_ID');
      SELECT code || ' ' || name INTO n FROM mm_item WHERE id = id_;
      copy(n, 'RL.ITEM_TEXT');
    END IF;
  END;

  -- the messages of the database in words: the constraint by its name, MM_CORE as it is
  FUNCTION friendly(p_dbtext VARCHAR2) RETURN VARCHAR2 IS
    p PLS_INTEGER := instr(p_dbtext, 'MM-1');
    c VARCHAR2(128);
  BEGIN
    IF p > 0 THEN
      RETURN rtrim(substr(p_dbtext, p, instr(p_dbtext || chr(10), chr(10), p) - p));
    END IF;
    p := instr(p_dbtext, '(MM.');
    IF p > 0 THEN
      c := substr(p_dbtext, p + 4, instr(p_dbtext, ')', p) - p - 4);
    END IF;
    RETURN CASE c
      WHEN 'MM_ITEM_CODE_UK' THEN 'Υπάρχει ήδη είδος με αυτόν τον κωδικό'
      WHEN 'MM_ITEM_BARCODE_UK' THEN 'Υπάρχει ήδη είδος με αυτό το barcode'
      WHEN 'MM_ITEM_BARCODE_CK' THEN 'Το barcode θέλει 8, 12, 13 ή 14 ψηφία'
      WHEN 'MM_ITEM_PRICE_CK' THEN 'Η τιμή δεν μπορεί να είναι αρνητική'
      WHEN 'MM_ITEM_COST_CK' THEN 'Το κόστος δεν μπορεί να είναι αρνητικό'
      WHEN 'MM_ITEM_MIN_CK' THEN 'Το ελάχιστο απόθεμα δεν μπορεί να είναι αρνητικό'
      WHEN 'MM_DOC_LINE_ITEM_FK' THEN 'Το είδος έχει παραστατικά: δεν σβήνεται, κάνε το ανενεργό'
      WHEN 'MM_STOCK_MOVE_ITEM_FK' THEN 'Το είδος έχει κινήσεις αποθήκης: δεν σβήνεται, κάνε το ανενεργό'
      WHEN 'MM_COUNT_LINE_ITEM_FK' THEN 'Το είδος είναι σε απογραφή: δεν σβήνεται, κάνε το ανενεργό'
      WHEN 'MM_CUSTOMER_AFM_UK' THEN 'Υπάρχει ήδη πελάτης με αυτό το ΑΦΜ'
      WHEN 'MM_SUPPLIER_AFM_UK' THEN 'Υπάρχει ήδη προμηθευτής με αυτό το ΑΦΜ'
      WHEN 'MM_CUSTOMER_AFM_CK' THEN 'Το ΑΦΜ θέλει 9 ψηφία'
      WHEN 'MM_SUPPLIER_AFM_CK' THEN 'Το ΑΦΜ θέλει 9 ψηφία'
      WHEN 'MM_CUSTOMER_EMAIL_CK' THEN 'Το email δεν είναι σωστό'
      WHEN 'MM_SUPPLIER_EMAIL_CK' THEN 'Το email δεν είναι σωστό'
      WHEN 'MM_DOC_CUSTOMER_FK' THEN 'Ο πελάτης έχει παραστατικά: δεν σβήνεται, κάνε τον ανενεργό'
      WHEN 'MM_DOC_SUPPLIER_FK' THEN 'Ο προμηθευτής έχει παραστατικά: δεν σβήνεται, κάνε τον ανενεργό'
      ELSE p_dbtext
    END;
  END;

  PROCEDURE on_error(p_code NUMBER, p_type VARCHAR2, p_text VARCHAR2, p_dbtext VARCHAR2) IS
  BEGIN
    -- FRM-40508/40509/40510: insert, update, delete failed; the reason is in DBMS_ERROR_TEXT
    IF p_code IN (40508, 40509, 40510) AND p_dbtext IS NOT NULL THEN
      message(friendly(p_dbtext));
    ELSE
      message(p_type || '-' || to_char(p_code) || ': ' || p_text);
    END IF;
  END;
END;

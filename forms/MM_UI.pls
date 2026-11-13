-- MM_UI.pls -- the package UI of the forms of the mini market (MM_ITEMS, MM_CUSTOMERS,
-- MM_SUPPLIERS): mkforms.py puts it in each form. The triggers only call it:
--   WHEN-NEW-FORM-INSTANCE  ui.init
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
  PROCEDURE on_error(p_code NUMBER, p_type VARCHAR2, p_text VARCHAR2, p_dbtext VARCHAR2);
  FUNCTION friendly(p_dbtext VARCHAR2) RETURN VARCHAR2;
END;
-- BODY
PACKAGE BODY ui IS
  c_block CONSTANT VARCHAR2(30) := 'BLOCK'; -- BLOCK

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
    execute_query;
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
          execute_query;
          set_block_property(c_block, DEFAULT_WHERE, '');
        END IF;
      END IF;
    ELSIF p_item = 'CTL.ALL' THEN
      copy('', 'CTL.FIND_TEXT');
      go_block(c_block);
      set_block_property(c_block, DEFAULT_WHERE, '');
      execute_query;
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
    n VARCHAR2(100);
    r NUMBER;
    s NUMBER;
  BEGIN
    IF p_block = 'ITEM' THEN
      BEGIN
        SELECT c.name, v.rate, i.stock INTO n, r, s
        FROM mm_item i, mm_category c, mm_vat v
        WHERE i.id = to_number(name_in('ITEM.ID')) AND c.id = i.category_id AND v.code = i.vat_code;
        copy(n, 'ITEM.CAT_NAME');
        copy(to_char(r), 'ITEM.VAT_RATE');
        copy(to_char(s), 'ITEM.STOCK');
      EXCEPTION
        WHEN no_data_found THEN NULL;
      END;
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

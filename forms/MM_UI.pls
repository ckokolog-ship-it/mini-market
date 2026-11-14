-- MM_UI.pls -- the package UI of the forms of the mini market (MM_ITEMS, MM_CUSTOMERS,
-- MM_SUPPLIERS, MM_CARDS, MM_RESERVATIONS, MM_KITS, MM_PROMOS, MM_VARIANTS, MM_INVOICES, the menu MM_MAIN):
-- mkforms.py puts it in each form. The triggers only call it:
--   WHEN-NEW-FORM-INSTANCE  ui.init
--   WHEN-NEW-RECORD-INSTANCE ui.master(:SYSTEM.TRIGGER_BLOCK)   (a master: its detail again)
--   WHEN-BUTTON-PRESSED     ui.press(:SYSTEM.TRIGGER_ITEM)   (the toolbar: ui.tool)
--   WHEN-VALIDATE-ITEM      ui.validate(:SYSTEM.TRIGGER_ITEM)
--   POST-QUERY              ui.post_query(:SYSTEM.TRIGGER_BLOCK)
--   ON-ERROR                ui.on_error(ERROR_CODE, ERROR_TYPE, ERROR_TEXT, DBMS_ERROR_TEXT)
-- Items through NAME_IN and COPY (no :BLOCK.ITEM): so tests/test_forms.py compiles and runs it in
-- the database, without the Forms. Every Greek string here becomes mm_text.t('T...') (mkforms.py).
PACKAGE ui IS
  PROCEDURE init;
  PROCEDURE press(p_item VARCHAR2);
  PROCEDURE tool(p_item VARCHAR2);
  PROCEDURE dblclick(p_item VARCHAR2);
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
  c_detail2 CONSTANT VARCHAR2(30) := ''; -- DETAIL2
  g_master NUMBER;                  -- the master whose detail is on the screen
  g_detail NUMBER;                  -- the record of the detail whose own detail is on the screen

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
    IF c_block IS NOT NULL THEN          -- (the menu has no block of a table)
      go_block(c_block);
      set_block_property(c_block, DEFAULT_WHERE, c_where);
      execute_query;
    END IF;
  END;

  -- the detail of the master record on the screen (once for each master record: going back to the
  -- master brings this trigger again)
  -- (three levels: the detail is the master of c_detail2, e.g. an invoice, its lines, their serials)
  PROCEDURE master(p_block VARCHAR2) IS
    id_ NUMBER := num(p_block || '.ID');
  BEGIN
    IF id_ IS NULL THEN
      RETURN;
    END IF;
    IF p_block = c_block AND c_detail IS NOT NULL THEN
      IF id_ = g_master THEN
        RETURN;
      END IF;
      g_master := id_;
      g_detail := NULL;
      go_block(c_detail);
      execute_query;
      go_block(c_block);
    ELSIF p_block = c_detail AND c_detail2 IS NOT NULL THEN
      IF id_ = g_detail THEN
        RETURN;
      END IF;
      g_detail := id_;
      go_block(c_detail2);
      execute_query;
      go_block(c_detail);
    END IF;
  END;

  PROCEDURE again(p_block VARCHAR2) IS
  BEGIN
    g_master := NULL;
    g_detail := NULL;
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
  -- a date typed in CTL (text DD/MM/YYYY: the same on every runtime)
  FUNCTION date_in(p_item VARCHAR2) RETURN DATE IS
  BEGIN
    RETURN to_date(name_in(p_item), 'DD/MM/YYYY');
  END;

  -- after a new master record made from CTL: it alone on the screen
  PROCEDURE show_only(p_id NUMBER) IS
  BEGIN
    go_block(c_block);
    set_block_property(c_block, DEFAULT_WHERE, 'id = ' || to_char(p_id));
    again(c_block);
  END;

  PROCEDURE action(p_item VARCHAR2) IS
    v NUMBER;
    n NUMBER;
    s NUMBER;
    pin VARCHAR2(40);
    tr VARCHAR2(1);
    sd VARCHAR2(1);
  BEGIN
    IF p_item LIKE 'CTL.GO\_%' ESCAPE '\' THEN           -- the menu: the form of the button
      call_form(substr(p_item, 8));
      RETURN;
    ELSIF p_item = 'CTL.EXIT' THEN
      exit_form;
      RETURN;
    ELSIF p_item = 'CTL.LOAD' THEN
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
      v := mm_core.new_reservation(name_in('CTL.R_NAME'), name_in('CTL.R_PHONE'), date_in('CTL.R_DATE'));
      forms_ddl('COMMIT');
      copy('', 'CTL.R_NAME');
      copy('', 'CTL.R_PHONE');
      show_only(v);
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
    -- the baskets: a component in or out (0), a new basket from an item, assemble (negative: apart)
    ELSIF p_item = 'CTL.ADDCOMP' THEN
      v := nvl(num('CTL.NEWKIT_ID'), num('KIT.ID'));
      mm_core.set_component(v, num('CTL.COMP_ID'), nvl(num('CTL.COMP_QTY'), 1));
      forms_ddl('COMMIT');
      copy('', 'CTL.COMP_ID');
      copy('', 'CTL.COMP_TEXT');
      IF name_in('CTL.NEWKIT_ID') IS NOT NULL THEN
        copy('', 'CTL.NEWKIT_ID');
        copy('', 'CTL.NEWKIT_TEXT');
        show_only(v);
      ELSE
        again('KC');
      END IF;
    ELSIF p_item = 'CTL.ASSEMBLE' THEN
      n := num('CTL.ASM_QTY');
      mm_core.assemble_kit(num('KIT.ID'), n);
      forms_ddl('COMMIT');
      again(c_block);
      message('Καλάθια: ' || to_char(n));
    -- the promotions: new, an item or a category in (0: out), active or not
    ELSIF p_item = 'CTL.NEWPROMO' THEN
      v := mm_core.new_promo(name_in('CTL.P_NAME'), upper(name_in('CTL.P_KIND')), date_in('CTL.P_FROM'), date_in('CTL.P_TO'),
                             num('CTL.P_PCT'), num('CTL.P_BUY'), num('CTL.P_FREE'), num('CTL.P_PRICE'));
      forms_ddl('COMMIT');
      copy('', 'CTL.P_NAME');
      show_only(v);
      message('Νέα προσφορά: βάλε τα είδη ή τις κατηγορίες της');
    ELSIF p_item = 'CTL.ADDPI' THEN
      mm_core.promo_item(num('PROMO.ID'), num('CTL.PI_ITEM_ID'), num('CTL.PI_CAT_ID'), nvl(num('CTL.PI_QTY'), 1));
      forms_ddl('COMMIT');
      copy('', 'CTL.PI_ITEM_ID');
      copy('', 'CTL.PI_ITEM_TEXT');
      copy('', 'CTL.PI_CAT_ID');
      copy('', 'CTL.PI_CAT_TEXT');
      again('PI');
    ELSIF p_item = 'CTL.TOGGLE' THEN
      mm_core.promo_active(num('PROMO.ID'), CASE name_in('PROMO.ACTIVE') WHEN 'Y' THEN 'N' ELSE 'Y' END);
      forms_ddl('COMMIT');
      again(c_block);
    -- clothes and shoes: a new variant (of the model, or of an item that becomes a model), one price
    ELSIF p_item = 'CTL.NEWVAR' THEN
      v := nvl(num('CTL.NEWMODEL_ID'), num('MODEL.ID'));
      n := mm_core.make_variant(v, num('CTL.V_COLOR_ID'), num('CTL.V_SIZE_ID'), name_in('CTL.V_BARCODE'));
      forms_ddl('COMMIT');
      copy('', 'CTL.V_BARCODE');
      IF name_in('CTL.NEWMODEL_ID') IS NOT NULL THEN
        copy('', 'CTL.NEWMODEL_ID');
        copy('', 'CTL.NEWMODEL_TEXT');
        show_only(v);
      ELSE
        again('VG');
      END IF;
    ELSIF p_item = 'CTL.MPRICE' THEN
      mm_core.model_price(num('MODEL.ID'), num('CTL.M_PRICE'));
      forms_ddl('COMMIT');
      again(c_block);
    -- invoicing: a new document (alone on the screen: its totals and lines as they change), a line
    -- (a card of mobile phones in a sale: as many cards, with their serials), post, cancel, credit
    ELSIF p_item = 'CTL.NEWDOC' THEN
      v := mm_core.new_doc(upper(name_in('CTL.D_TYPE')), num('CTL.CUST_ID'), num('CTL.SUPP_ID'), NULL,
                           upper(nvl(name_in('CTL.D_PAY'), 'CREDIT')), date_in('CTL.D_DATE'));
      forms_ddl('COMMIT');
      show_only(v);
      message('Νέο πρόχειρο: βάλε τις γραμμές του και καταχώρισέ το');
    ELSIF p_item = 'CTL.ADDLINE' THEN
      v := num('DOC.ID');
      s := num('CTL.L_ITEM_ID');
      SELECT i.serial_tracked, t.side, t.stock_sign INTO tr, sd, n
      FROM mm_doc d, mm_doc_type t, mm_item i
      WHERE d.id = v AND t.code = d.doc_type AND i.id = s;
      IF tr = 'Y' AND sd = 'S' AND n = -1 THEN
        n := mm_core.sell_serials(v, s, nvl(num('CTL.L_QTY'), 1));
      ELSE
        n := mm_core.add_line(v, s, nvl(num('CTL.L_QTY'), 1), num('CTL.L_PRICE'), nvl(num('CTL.L_DISC'), 0));
      END IF;
      forms_ddl('COMMIT');
      copy('', 'CTL.L_ITEM_ID');
      copy('', 'CTL.L_ITEM_TEXT');
      copy('', 'CTL.L_PRICE');
      copy('', 'CTL.L_DISC');
      show_only(v);
    ELSIF p_item = 'CTL.DELLINE' THEN
      v := num('DOC.ID');
      mm_core.delete_line(num('DL.ID'));
      forms_ddl('COMMIT');
      show_only(v);
    ELSIF p_item = 'CTL.POSTDOC' THEN
      v := num('DOC.ID');
      n := mm_core.post_doc(v);
      forms_ddl('COMMIT');
      show_only(v);
      message('Καταχωρήθηκε με αριθμό ' || to_char(n));
    ELSIF p_item = 'CTL.CANCELDOC' THEN
      v := num('DOC.ID');
      mm_core.cancel_doc(v);
      forms_ddl('COMMIT');
      show_only(v);
      message('Ακυρώθηκε');
    ELSIF p_item = 'CTL.CREDIT' THEN
      v := mm_core.credit_note(num('DOC.ID'));
      forms_ddl('COMMIT');
      show_only(v);
      message('Πρόχειρο πιστωτικό: έλεγξε τις γραμμές και καταχώρισέ το');
    -- the serials of a line of cards: a sale takes this card (scanned) in its line, or gives one
    -- back; a purchase loads this card (and its PIN) in the line chosen
    ELSIF p_item = 'CTL.ADDSER' THEN
      v := num('DOC.ID');
      SELECT t.side, t.stock_sign INTO sd, n FROM mm_doc d, mm_doc_type t WHERE d.id = v AND t.code = d.doc_type;
      IF sd = 'S' AND n = -1 THEN
        n := mm_core.sell_serial(v, NULL, name_in('CTL.S_SERIAL'));
      ELSE
        n := mm_core.add_serial(num('DL.ID'), name_in('CTL.S_SERIAL'), name_in('CTL.S_PIN'));
      END IF;
      forms_ddl('COMMIT');
      copy('', 'CTL.S_SERIAL');
      copy('', 'CTL.S_PIN');
      show_only(v);
      message('Το serial μπήκε');
    ELSIF p_item = 'CTL.DELSER' THEN
      v := num('DOC.ID');
      mm_core.release_serial(num('DS.ID'));
      forms_ddl('COMMIT');
      show_only(v);
      message('Η κάρτα γύρισε στις διαθέσιμες');
    ELSIF p_item = 'CTL.DELDOC' THEN
      mm_core.delete_doc(num('DOC.ID'));
      forms_ddl('COMMIT');
      go_block(c_block);
      set_block_property(c_block, DEFAULT_WHERE, c_where);
      again(c_block);
      message('Το πρόχειρο σβήστηκε');
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

  -- the toolbar: the keys of the Forms on the block of the cursor (the buttons do not take it)
  PROCEDURE tool(p_item VARCHAR2) IS
  BEGIN
    IF p_item = 'TB.T_SAVE' THEN
      do_key('COMMIT_FORM');
    ELSIF p_item = 'TB.T_ENTERQ' THEN
      do_key('ENTER_QUERY');
    ELSIF p_item = 'TB.T_EXECQ' THEN
      do_key('EXECUTE_QUERY');
    ELSIF p_item = 'TB.T_NEW' THEN
      do_key('CREATE_RECORD');
    ELSIF p_item = 'TB.T_DEL' THEN
      do_key('DELETE_RECORD');
    ELSIF p_item = 'TB.T_LOV' THEN
      do_key('LIST_VALUES');           -- the list of the item of the cursor
    ELSIF p_item = 'TB.T_PREV' THEN
      do_key('PREVIOUS_RECORD');
    ELSIF p_item = 'TB.T_NEXT' THEN
      do_key('NEXT_RECORD');
    ELSIF p_item = 'TB.T_MAIN' THEN
      new_form('MM_MAIN');
    ELSIF p_item = 'TB.T_EXIT' THEN
      do_key('EXIT_FORM');
    END IF;
  END;

  -- a double click on an item with a list: the list (F9 is not the key of the list on the web)
  PROCEDURE dblclick(p_item VARCHAR2) IS
  BEGIN
    IF p_item IS NOT NULL AND get_item_property(p_item, LOV_NAME) IS NOT NULL THEN
      do_key('LIST_VALUES');
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
    z VARCHAR2(40);
    r NUMBER;
    s NUMBER;
    a NUMBER;
    id_ NUMBER;
    c_ NUMBER;
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
    ELSIF p_block = 'DOC' THEN
      c_ := num('DOC.CUSTOMER_ID');
      id_ := num('DOC.SUPPLIER_ID');
      n := NULL;
      IF c_ IS NOT NULL THEN
        SELECT name INTO n FROM mm_customer WHERE id = c_;
      ELSIF id_ IS NOT NULL THEN
        SELECT name INTO n FROM mm_supplier WHERE id = id_;
      END IF;
      copy(n, 'DOC.PARTNER_TEXT');
    ELSIF p_block = 'DL' THEN
      id_ := num('DL.ITEM_ID');
      SELECT code || ' ' || name INTO n FROM mm_item WHERE id = id_;
      copy(n, 'DL.ITEM_TEXT');
    ELSIF p_block = 'RL' THEN
      id_ := num('RL.ITEM_ID');
      SELECT code || ' ' || name INTO n FROM mm_item WHERE id = id_;
      copy(n, 'RL.ITEM_TEXT');
    ELSIF p_block = 'KIT' THEN
      id_ := num('KIT.ID');
      SELECT ready, can_make INTO s, a FROM mm_kit_avail WHERE kit_id = id_;
      copy(to_char(s), 'KIT.STOCK');
      copy(to_char(a), 'KIT.CAN_MAKE');
    ELSIF p_block = 'KC' THEN
      id_ := num('KC.COMPONENT_ID');
      SELECT code || ' ' || name, stock INTO n, s FROM mm_item WHERE id = id_;
      copy(n, 'KC.COMP_TEXT');
      copy(to_char(s), 'KC.COMP_STOCK');
    ELSIF p_block = 'PI' THEN
      -- (no SELECT inside a function: the PL/SQL of the Forms does not take it, PL/SQL 103)
      id_ := num('PI.ITEM_ID');
      c_ := num('PI.CATEGORY_ID');
      IF id_ IS NOT NULL THEN
        SELECT code || ' ' || name INTO n FROM mm_item WHERE id = id_;
      ELSE
        SELECT name INTO n FROM mm_category WHERE id = c_;
      END IF;
      copy(n, 'PI.TEXT');
    ELSIF p_block = 'VG' THEN
      id_ := num('VG.ID');
      SELECT c.name, sz.code, av.stock, av.available INTO n, z, s, a
      FROM mm_item v, mm_color c, mm_size sz, mm_item_avail av
      WHERE v.id = id_ AND c.id (+) = v.color_id AND sz.id (+) = v.size_id AND av.item_id = v.id;
      copy(n, 'VG.COLOR_TEXT');
      copy(z, 'VG.SIZE_TEXT');
      copy(to_char(s), 'VG.STOCK');
      copy(to_char(a), 'VG.AVAIL');
    END IF;
    -- what this procedure put in the items of the record is not a change of the user: the record
    -- as it came from the database (else a LOV that validates from its list writes its db item
    -- again when the cursor passes, and the form asks to save what nobody changed)
    set_record_property(to_number(name_in('SYSTEM.TRIGGER_RECORD')), p_block, STATUS, QUERY_STATUS);
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

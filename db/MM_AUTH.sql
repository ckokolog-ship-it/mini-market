-- MM_AUTH.sql -- the users of the shop and their logins (step 7a). Run by INSTALL.sql. Needs
-- DBMS_CRYPTO (GRANT_CRYPTO.sql, as SYS: the same grant as MM_PIN).
--
--   mm_auth.create_user('maria', 'Μαρία Π.', 'CASHIER', :password)     a user (ADMIN, MANAGER, CASHIER)
--   mm_auth.login('maria', :password, 'web', token, role, expires)       a session of 12 hours: its token
--   mm_auth.check(token, user_id, username, role)                         who it is (else MM-179)
--   mm_auth.logout(token)
--   set_password, set_role, set_active, unlock
--   mm_auth.set_place('maria', :store, :register)                       where she works (may_use: a register)
--
-- The password: PBKDF2-HMAC-SHA256, its own random salt of 16 bytes, C_ITER rounds (kept for each user:
-- more rounds later take effect at its next password). The token: 32 random bytes as 64 hex
-- characters, given once; only its SHA-256 is kept (MM_SESSION). 5 wrong passwords in a row: locked for
-- 15 minutes. An unknown user costs the same time as a known one (no hint by the clock).
-- No commit here, as MM_CORE: except what a failed login leaves (its count, the log), which stays.
-- The errors: MM-174 .. MM-182.
create or replace package mm_auth as
  c_iter constant pls_integer := 100000;
  c_hours constant pls_integer := 12;

  function create_user(p_username varchar2, p_full_name varchar2, p_role varchar2,
                       p_password varchar2) return number;
  procedure set_password(p_username varchar2, p_password varchar2);
  procedure set_role(p_username varchar2, p_role varchar2);
  procedure set_active(p_username varchar2, p_active varchar2);
  procedure unlock(p_username varchar2);
  -- the place of a user: its store (a warehouse) and its register (of that store: a register given alone,
  -- its store too); null, null: everywhere. A cashier with a register works only on it; with a store,
  -- on the registers of it; a manager, on the registers of its store; an administrator, everywhere.
  procedure set_place(p_username varchar2, p_warehouse_id number, p_register_id number default null);
  -- may the user work on the register: Y or N
  function may_use(p_user_id number, p_register_id number) return varchar2;
  procedure login(p_username varchar2, p_password varchar2, p_client varchar2,
                  o_token out varchar2, o_role out varchar2, o_expires out date);
  procedure check_token(p_token varchar2, o_user_id out number, o_username out varchar2, o_role out varchar2);
  procedure logout(p_token varchar2);
  -- the password as stored (for the tests: the same in Python)
  function pbkdf2(p_password varchar2, p_salt raw, p_iter pls_integer) return raw;
end mm_auth;
/

create or replace package body mm_auth as

  procedure fail(p_no pls_integer, p_text varchar2) is
  begin
    raise_application_error(-20100 - p_no, 'MM-' || to_char(100 + p_no) || ': ' || p_text);
  end;

  procedure note(p_username varchar2, p_event varchar2, p_client varchar2 default null) is
  begin
    insert into mm_auth_log (username, event, client) values (substr(p_username, 1, 30), p_event, substr(p_client, 1, 60));
  end;

  -- a failed login is remembered even though the call fails (its own transaction)
  procedure failed(p_username varchar2, p_client varchar2, p_locked boolean) is
    pragma autonomous_transaction;
  begin
    update mm_user
    set failed = failed + 1,
        locked_until = case when failed + 1 >= 5 then sysdate + 15 / 1440 else locked_until end
    where username = p_username;
    note(p_username, case when p_locked then 'LOCKED' else 'FAIL' end, p_client);
    commit;
  end;

  function pbkdf2(p_password varchar2, p_salt raw, p_iter pls_integer) return raw is
    k raw(2000) := utl_i18n.string_to_raw(p_password, 'AL32UTF8');
    u raw(32);
    t raw(32);
  begin
    u := dbms_crypto.mac(utl_raw.concat(p_salt, hextoraw('00000001')), dbms_crypto.hmac_sh256, k);
    t := u;
    for i in 2 .. p_iter loop
      u := dbms_crypto.mac(u, dbms_crypto.hmac_sh256, k);
      t := utl_raw.bit_xor(t, u);
    end loop;
    return t;
  end;

  procedure check_password(p_password varchar2) is
  begin
    if p_password is null or length(p_password) < 10 or length(p_password) > 200
       or not regexp_like(p_password, '[[:alpha:]]') or not regexp_like(p_password, '[[:digit:]]') then
      fail(75, 'Ο κωδικός θέλει τουλάχιστον 10 χαρακτήρες, με γράμματα και ψηφία');
    end if;
  end;

  procedure check_role(p_role varchar2) is
  begin
    if p_role is null or p_role not in ('CASHIER', 'MANAGER', 'ADMIN') then
      fail(76, 'Ρόλος: CASHIER (ταμίας), MANAGER (προϊστάμενος) ή ADMIN (διαχειριστής)');
    end if;
  end;

  function user_id(p_username varchar2) return number is
    v number;
  begin
    select id into v from mm_user where username = lower(p_username);
    return v;
  exception
    when no_data_found then fail(80, 'Δεν υπάρχει χρήστης ' || p_username);
  end;

  -- the level of a user (MM_USER.ROLE) is also its role of the system (MM_RIGHTS: MM_USER_ROLE): the one of
  -- its old level out, the new one in; its other roles stay
  procedure in_role(p_user_id number, p_role varchar2) is
  begin
    delete from mm_user_role where user_id = p_user_id
      and role_id in (select id from mm_role where system = 'Y' and code <> p_role);
    insert into mm_user_role (user_id, role_id)
    select p_user_id, r.id from mm_role r
    where r.code = p_role and not exists (select 1 from mm_user_role x where x.user_id = p_user_id and x.role_id = r.id);
  end;

  -- the shop never stays without an active administrator
  procedure keep_an_admin(p_except number) is
    n number;
  begin
    select count(*) into n from mm_user where role = 'ADMIN' and active = 'Y' and id <> p_except;
    if n = 0 then
      fail(81, 'Πρέπει να μείνει τουλάχιστον ένας ενεργός διαχειριστής');
    end if;
  end;

  function create_user(p_username varchar2, p_full_name varchar2, p_role varchar2,
                       p_password varchar2) return number is
    s raw(16) := dbms_crypto.randombytes(16);
    v number;
  begin
    if p_username is null or not regexp_like(lower(p_username), '^[a-z][a-z0-9._-]{2,29}$') then
      fail(74, 'Όνομα χρήστη: 3 έως 30 λατινικά γράμματα, ψηφία ή . _ -, από γράμμα');
    end if;
    check_role(upper(p_role));
    check_password(p_password);
    begin
      insert into mm_user (username, full_name, role, pw_hash, pw_salt, pw_iter)
      values (lower(p_username), p_full_name, upper(p_role), pbkdf2(p_password, s, c_iter), s, c_iter)
      returning id into v;
    exception
      when dup_val_on_index then fail(82, 'Υπάρχει ήδη χρήστης ' || lower(p_username));
    end;
    in_role(v, upper(p_role));
    note(lower(p_username), 'CREATE');
    return v;
  end;

  procedure set_password(p_username varchar2, p_password varchar2) is
    id_ number := user_id(p_username);
    s raw(16) := dbms_crypto.randombytes(16);
  begin
    check_password(p_password);
    update mm_user set pw_hash = pbkdf2(p_password, s, c_iter), pw_salt = s, pw_iter = c_iter,
                       pw_changed_at = sysdate, failed = 0, locked_until = null
    where id = id_;
    -- a new password: the sessions of the old one end
    update mm_session set revoked = 'Y' where user_id = id_;
    note(lower(p_username), 'PASSWORD');
  end;

  procedure set_role(p_username varchar2, p_role varchar2) is
    id_ number := user_id(p_username);
  begin
    check_role(upper(p_role));
    if upper(p_role) <> 'ADMIN' then
      keep_an_admin(id_);
    end if;
    update mm_user set role = upper(p_role) where id = id_;
    in_role(id_, upper(p_role));
    update mm_session set revoked = 'Y' where user_id = id_;
    note(lower(p_username), 'ROLE');
  end;

  procedure set_active(p_username varchar2, p_active varchar2) is
    id_ number := user_id(p_username);
  begin
    if p_active is null or p_active not in ('Y', 'N') then
      fail(80, 'Ενεργός: Y ή N');
    end if;
    if p_active = 'N' then
      keep_an_admin(id_);
      update mm_session set revoked = 'Y' where user_id = id_;
    end if;
    update mm_user set active = p_active where id = id_;
    note(lower(p_username), 'ACTIVE');
  end;

  procedure set_place(p_username varchar2, p_warehouse_id number, p_register_id number default null) is
    id_ number := user_id(p_username);
    wh number := p_warehouse_id;
    rwh number;
    n number;
  begin
    if p_register_id is not null then
      begin
        select nvl(warehouse_id, (select min(id) from mm_warehouse where main = 'Y')) into rwh
        from mm_register where id = p_register_id and active = 'Y';
      exception
        when no_data_found then fail(96, 'Δεν υπάρχει ενεργό ταμείο ' || p_register_id);
      end;
      if wh is null then
        wh := rwh;
      elsif wh <> rwh then
        fail(96, 'Το ταμείο του χρήστη πρέπει να είναι του καταστήματός του');
      end if;
    end if;
    if wh is not null then
      select count(*) into n from mm_warehouse where id = wh and active = 'Y';
      if n = 0 then
        fail(96, 'Δεν υπάρχει ενεργό κατάστημα ' || wh);
      end if;
    end if;
    update mm_user set warehouse_id = wh, register_id = p_register_id where id = id_;
    note(lower(p_username), 'PLACE');
  end;

  function may_use(p_user_id number, p_register_id number) return varchar2 is
    u mm_user%rowtype;
    rwh number;
  begin
    select * into u from mm_user where id = p_user_id;
    select nvl(warehouse_id, (select min(id) from mm_warehouse where main = 'Y')) into rwh
    from mm_register where id = p_register_id;
    if u.role = 'ADMIN' or u.warehouse_id is null and u.register_id is null then
      return 'Y';
    elsif u.role = 'CASHIER' and u.register_id is not null then
      return case when u.register_id = p_register_id then 'Y' else 'N' end;
    else
      return case when rwh = u.warehouse_id then 'Y' else 'N' end;
    end if;
  exception
    when no_data_found then return 'N';
  end;

  procedure unlock(p_username varchar2) is
    id_ number := user_id(p_username);
  begin
    update mm_user set failed = 0, locked_until = null where id = id_;
    note(lower(p_username), 'UNLOCK');
  end;

  procedure login(p_username varchar2, p_password varchar2, p_client varchar2,
                  o_token out varchar2, o_role out varchar2, o_expires out date) is
    u mm_user%rowtype;
    h raw(32);
    tok raw(32);
  begin
    begin
      select * into u from mm_user where username = lower(p_username);
    exception
      when no_data_found then
        h := pbkdf2(nvl(p_password, 'x'), hextoraw('00000000000000000000000000000000'), c_iter);  -- the same time
        note(lower(substr(p_username, 1, 30)), 'FAIL', p_client);
        fail(77, 'Λάθος όνομα χρήστη ή κωδικός');
    end;
    if u.locked_until > sysdate then
      failed(u.username, p_client, true);
      fail(78, 'Ο λογαριασμός κλειδώθηκε για λίγα λεπτά, μετά από πολλούς λάθος κωδικούς');
    end if;
    h := pbkdf2(nvl(p_password, 'x'), u.pw_salt, u.pw_iter);
    if h <> u.pw_hash or u.active <> 'Y' then
      failed(u.username, p_client, false);
      fail(77, 'Λάθος όνομα χρήστη ή κωδικός');
    end if;
    update mm_user set failed = 0, locked_until = null where id = u.id;
    tok := dbms_crypto.randombytes(32);
    o_token := lower(rawtohex(tok));
    o_role := u.role;
    o_expires := sysdate + c_hours / 24;
    insert into mm_session (token_hash, user_id, client, expires_at)
    values (dbms_crypto.hash(utl_i18n.string_to_raw(o_token, 'AL32UTF8'), dbms_crypto.hash_sh256), u.id,
            substr(p_client, 1, 60), o_expires);
    note(u.username, 'LOGIN', p_client);
  end;

  procedure check_token(p_token varchar2, o_user_id out number, o_username out varchar2, o_role out varchar2) is
    h raw(32);
  begin
    if p_token is null or not regexp_like(p_token, '^[0-9a-f]{64}$') then
      fail(79, 'Χρειάζεται σύνδεση');
    end if;
    h := dbms_crypto.hash(utl_i18n.string_to_raw(p_token, 'AL32UTF8'), dbms_crypto.hash_sh256);
    select u.id, u.username, u.role into o_user_id, o_username, o_role
    from mm_session s join mm_user u on u.id = s.user_id
    where s.token_hash = h and s.revoked = 'N' and s.expires_at > sysdate and u.active = 'Y';
    update mm_session set last_seen = sysdate where token_hash = h and last_seen < sysdate - 1 / 1440;
  exception
    when no_data_found then fail(79, 'Χρειάζεται σύνδεση');
  end;

  procedure logout(p_token varchar2) is
    u number;
    n varchar2(30);
    r varchar2(10);
  begin
    check_token(p_token, u, n, r);
    update mm_session set revoked = 'Y'
    where token_hash = dbms_crypto.hash(utl_i18n.string_to_raw(p_token, 'AL32UTF8'), dbms_crypto.hash_sh256);
    note(n, 'LOGOUT');
  end;
end mm_auth;
/

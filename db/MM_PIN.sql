-- MM_PIN.sql -- the PINs of the cards, encrypted: AES-256, CBC, PKCS5, a random IV for each PIN
-- (stored in front of it). The key: 32 random bytes in MM_SECRET, made the first time.
-- Needs EXECUTE on SYS.DBMS_CRYPTO (GRANT_CRYPTO.sql, as SYS). Without it this package is not valid
-- and only the PINs do not work; MM_CORE and the rest do.
--
-- What it protects: the PINs do not show in a SELECT, a report, an export of a table or a backup
-- read by someone without the key. A session of the owner MM can still read the key: the real
-- wall is the login (step 7a), where the users of the shop are not MM.

create or replace package mm_pin as
  function enc(p_pin varchar2) return raw;
  function dec(p_enc raw) return varchar2;
end mm_pin;
/

create or replace package body mm_pin as
  c_type constant pls_integer := dbms_crypto.encrypt_aes256 + dbms_crypto.chain_cbc + dbms_crypto.pad_pkcs5;

  function key_ return raw is
    k raw(64);
  begin
    select value into k from mm_secret where name = 'PIN';
    return k;
  exception
    when no_data_found then
      begin
        insert into mm_secret (name, value) values ('PIN', dbms_crypto.randombytes(32));
      exception
        when dup_val_on_index then null;   -- another session made it at the same time
      end;
      select value into k from mm_secret where name = 'PIN';
      return k;
  end;

  function enc(p_pin varchar2) return raw is
    iv raw(16) := dbms_crypto.randombytes(16);
  begin
    if p_pin is null then
      return null;
    end if;
    return utl_raw.concat(iv, dbms_crypto.encrypt(utl_i18n.string_to_raw(p_pin, 'AL32UTF8'), c_type, key_, iv));
  end;

  function dec(p_enc raw) return varchar2 is
  begin
    if p_enc is null then
      return null;
    end if;
    return utl_i18n.raw_to_char(dbms_crypto.decrypt(utl_raw.substr(p_enc, 17), c_type, key_,
                                                    utl_raw.substr(p_enc, 1, 16)), 'AL32UTF8');
  end;
end mm_pin;
/

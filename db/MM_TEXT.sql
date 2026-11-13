-- MM_TEXT.sql -- made by forms/mkforms.py: the Greek of the forms (prompts, labels, titles,
-- messages), which the forms ask for when they open (XML2Forms does not carry Greek into a
-- form). UTF-8: run by INSTALL.sql, or by the build scripts with NLS_LANG ...AL32UTF8.
create or replace package mm_text as
  function t(p_key varchar2) return varchar2;
end mm_text;
/

create or replace package body mm_text as
  function t(p_key varchar2) return varchar2 is
  begin
    return case p_key
      when 'T0179355B' then 'Το είδος έχει κινήσεις αποθήκης: δεν σβήνεται, κάνε το ανενεργό'
      when 'T02DAB4A6' then 'Ελάχιστο'
      when 'T09ABDC37' then 'Ενεργός'
      when 'T0D330FC8' then 'Κόστος'
      when 'T0D71B1A9' then 'Ενεργό'
      when 'T10F856C7' then 'Τεμάχιο'
      when 'T1EC8273B' then 'Το είδος έχει παραστατικά: δεν σβήνεται, κάνε το ανενεργό'
      when 'T1F4CE438' then 'Υπάρχει ήδη είδος με αυτό το barcode'
      when 'T22238872' then 'Το barcode δεν είναι σωστό: 8, 12, 13 ή 14 ψηφία, με σωστό ψηφίο ελέγχου'
      when 'T256B17A1' then 'Πελάτης'
      when 'T2BA80546' then 'Προμηθευτής'
      when 'T2F06F576' then 'Τιμή λιαν.'
      when 'T318E92C7' then 'Κωδικός'
      when 'T32D94AD8' then 'Περιγραφή'
      when 'T333294D3' then 'ΔΟΥ'
      when 'T364317ED' then 'Κιλό'
      when 'T382D5390' then 'Όλα'
      when 'T39B36DC5' then 'Το είδος είναι σε απογραφή: δεν σβήνεται, κάνε το ανενεργό'
      when 'T3CCA1645' then 'ΦΠΑ'
      when 'T3DB645A5' then 'Είδη'
      when 'T4491B68A' then 'Κωδ.'
      when 'T49A1E700' then 'Η τιμή δεν μπορεί να είναι αρνητική'
      when 'T545A55C9' then 'Το email δεν είναι σωστό'
      when 'T579FA7CF' then 'Μονάδα'
      when 'T5E52D707' then 'Το barcode θέλει 8, 12, 13 ή 14 ψηφία'
      when 'T61C7FA29' then 'Διεύθυνση'
      when 'T62053325' then 'Το ΑΦΜ θέλει 9 ψηφία'
      when 'T6DD60741' then 'Λίτρο'
      when 'T6E196C2F' then 'Υπάρχει ήδη προμηθευτής με αυτό το ΑΦΜ'
      when 'T71D1363A' then 'Απόθεμα'
      when 'T794C9796' then 'Μονάδες'
      when 'T88ECCC37' then 'Το κόστος δεν μπορεί να είναι αρνητικό'
      when 'T996015D1' then 'Βρες...'
      when 'TA37878FE' then 'Το ελάχιστο απόθεμα δεν μπορεί να είναι αρνητικό'
      when 'TAD04A0D2' then 'Κατηγορίες'
      when 'TB806186A' then 'Υπάρχει ήδη είδος με αυτόν τον κωδικό'
      when 'TBDAED182' then 'Κατηγορία'
      when 'TDA378DB0' then 'Υπάρχει ήδη πελάτης με αυτό το ΑΦΜ'
      when 'TDC480307' then 'Προμηθευτές'
      when 'TE0832A2F' then 'Ο πελάτης έχει παραστατικά: δεν σβήνεται, κάνε τον ανενεργό'
      when 'TE70AB6C4' then 'Δεν επιτρέπεται αρνητικός αριθμός'
      when 'TEA0B7F9B' then 'Το ΑΦΜ δεν είναι σωστό: 9 ψηφία, με σωστό ψηφίο ελέγχου'
      when 'TEA5C76BB' then 'ΑΦΜ'
      when 'TF37AAB64' then 'Ο προμηθευτής έχει παραστατικά: δεν σβήνεται, κάνε τον ανενεργό'
      when 'TF8215E9F' then 'Τηλέφωνο'
      when 'TF89F7153' then 'Πελάτες'
      when 'TFFAE21CF' then 'Επωνυμία'
      else p_key
    end;
  end;
end mm_text;
/

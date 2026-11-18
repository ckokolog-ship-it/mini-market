package mm.api;

import java.sql.CallableStatement;
import java.sql.Connection;
import java.sql.SQLException;
import java.sql.Types;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * The roles, their rights and the menu (MM_RIGHTS), for the page «Ρόλοι και δικαιώματα»: the screen ROLES
 * (read: R, a change: W; Rights).
 *
 * <pre>
 *   GET  /api/roles                            the roles: their users, how many grants
 *   POST /api/roles {code, name}               a new role (no rights yet)
 *   POST /api/roles/{code} {name, active}      renamed, (not) active
 *   POST /api/roles/{code}/copy {from}         the rights of another role (what it had: replaced)
 *   POST /api/roles/{code}/delete              out (not a role of the system)
 *   GET  /api/roles/{code}/grants              the menu with what the role may do: each screen, its fields and
 *                                              actions: grant (its row: N R W, or null) and lvl (what it comes to)
 *   POST /api/roles/{code}/grants {screen, item, level}   one grant (level null: its row out)
 *   POST /api/users/{id}/roles {roles: [code]} the roles of a user (Api)
 *   GET  /api/menu                             the menu: its groups and screens, the inactive ones too
 *   POST /api/menu/{code} {name, sort_no, group, active}   renamed, moved, (not) active
 * </pre>
 */
final class Roles {
    private Roles() {
    }

    static Object get(Connection c, String[] p) throws SQLException {
        if ("menu".equals(p[0]) && p.length == 1) {
            return menu(c);
        }
        if (p.length == 1) {
            return roles(c);
        }
        if (p.length == 3 && "grants".equals(p[2])) {
            return grants(c, p[1]);
        }
        throw new Http.Fail(404, "not_found", "no such endpoint");
    }

    static Object post(Connection c, String[] p, Map<String, Object> in) throws SQLException {
        if ("menu".equals(p[0])) {
            if (p.length != 2) {
                throw new Http.Fail(404, "not_found", "no such endpoint");
            }
            Object sort = in.get("sort_no");
            Db.exec(c, "begin mm_rights.set_object(?, ?, ?, ?, ?); end;", p[1], Http.text(in, "name", true),
                    sort == null ? null : new java.math.BigDecimal(String.valueOf(sort)), Http.text(in, "group", false),
                    Boolean.FALSE.equals(in.get("active")) ? "N" : "Y");
            return menu(c);
        }
        if (p.length == 1) {
            try (CallableStatement cs = c.prepareCall("begin ? := mm_rights.create_role(?, ?); end;")) {
                cs.registerOutParameter(1, Types.NUMERIC);
                cs.setString(2, Http.text(in, "code", true));
                cs.setString(3, Http.text(in, "name", true));
                cs.execute();
            }
            return roles(c);
        }
        String code = p[1];
        if (p.length == 2) {
            Db.exec(c, "begin mm_rights.set_role(?, ?, ?); end;", code, Http.text(in, "name", false),
                    Boolean.FALSE.equals(in.get("active")) ? "N" : "Y");
            return roles(c);
        }
        switch (p[2]) {
            case "copy" -> {
                Db.exec(c, "begin mm_rights.copy_role(?, ?); end;", Http.text(in, "from", true), code);
                return grants(c, code);
            }
            case "delete" -> {
                Db.exec(c, "begin mm_rights.drop_role(?); end;", code);
                return roles(c);
            }
            case "grants" -> {
                String level = Http.text(in, "level", false);
                Db.exec(c, "begin mm_rights.set_grant(?, ?, ?, ?); end;", code, Http.text(in, "screen", true),
                        Http.text(in, "item", false), level == null || level.isBlank() ? null : level);
                return grants(c, code);
            }
            default -> throw new Http.Fail(404, "not_found", "no such endpoint");
        }
    }

    static Map<String, Object> roles(Connection c) throws SQLException {
        return Map.of("rows", Db.rows(c, """
                select r.id, r.code, r.name, r.all_rights, r.system, r.active,
                       (select count(*) from mm_user_role ur where ur.role_id = r.id) users,
                       (select count(*) from mm_grant g where g.role_id = r.id) grants
                from mm_role r order by case r.system when 'Y' then 0 else 1 end, r.id"""));
    }

    /** the menu with the rights of one role: grant (its own row) and lvl (what it comes to, MM_ROLE_RIGHT) */
    static Map<String, Object> grants(Connection c, String code) throws SQLException {
        List<Map<String, Object>> role = Db.rows(c, "select id, code, name, all_rights, system, active from mm_role where code = upper(?)", code);
        if (role.isEmpty()) {
            throw new Http.Fail(404, "not_found", "no such role: " + code);
        }
        Object rid = role.get(0).get("id");
        List<Map<String, Object>> rows = Db.rows(c, """
                select g.code group_code, g.name group_name, o.code, o.name, o.route, o.form, o.active,
                       i.code item_code, i.kind item_kind, i.name item_name,
                       (select x.lvl from mm_grant x where x.role_id = ? and x.object_id = o.id
                          and nvl(x.item_id, 0) = nvl(i.id, 0)) grant_lvl,
                       (select substr('NRW', r.lv + 1, 1) from mm_role_right r where r.role_id = ? and r.object_id = o.id
                          and nvl(r.item_id, 0) = nvl(i.id, 0)) lvl
                from mm_object o
                left join mm_object g on g.id = o.parent_id
                left join (select null id, null object_id, null code, null kind, null name, -1 sort_no from dual
                           union all select id, object_id, code, kind, name, sort_no from mm_object_item) i
                  on i.object_id = o.id or i.id is null
                where o.kind = 'S'
                order by g.sort_no, g.code, o.sort_no, o.code, i.sort_no""", rid, rid);
        List<Map<String, Object>> screens = new ArrayList<>();
        Map<String, Object> s = null;
        for (Map<String, Object> r : rows) {
            if (r.get("item_code") == null) {
                s = new LinkedHashMap<>();
                for (String k : new String[] {"group_code", "group_name", "code", "name", "route", "form", "active"}) {
                    s.put(k, r.get(k));
                }
                s.put("grant", r.get("grant_lvl"));
                s.put("lvl", r.get("lvl") == null ? "N" : r.get("lvl"));
                s.put("items", new ArrayList<Map<String, Object>>());
                screens.add(s);
            } else if (s != null) {
                Map<String, Object> i = new LinkedHashMap<>();
                i.put("code", r.get("item_code"));
                i.put("kind", r.get("item_kind"));
                i.put("name", r.get("item_name"));
                i.put("grant", r.get("grant_lvl"));
                i.put("lvl", r.get("lvl") == null ? "N" : r.get("lvl"));
                @SuppressWarnings("unchecked")
                List<Map<String, Object>> l = (List<Map<String, Object>>) s.get("items");
                l.add(i);
            }
        }
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("role", role.get(0));
        out.put("screens", screens);
        return out;
    }

    static Map<String, Object> menu(Connection c) throws SQLException {
        return Map.of("rows", Db.rows(c, """
                select o.code, o.kind, o.name, o.route, o.form, o.sort_no, o.active, g.code group_code
                from mm_object o left join mm_object g on g.id = o.parent_id
                order by nvl(g.sort_no, o.sort_no), nvl(g.code, o.code), case o.kind when 'G' then 0 else 1 end, o.sort_no, o.code"""));
    }

    /** the roles of a user: those given in, the others out (MM-198: never without an administrator) */
    static void userRoles(Connection c, String username, List<?> codes) throws SQLException {
        List<String> want = new ArrayList<>();
        for (Object o : codes) {
            want.add(String.valueOf(o).trim().toUpperCase(java.util.Locale.ROOT));
        }
        for (String r : want) {
            Db.exec(c, "begin mm_rights.add_user_role(?, ?); end;", username, r);
        }
        for (Map<String, Object> r : Db.rows(c, """
                select r.code from mm_user_role ur join mm_role r on r.id = ur.role_id join mm_user u on u.id = ur.user_id
                where u.username = ?""", username)) {
            if (!want.contains((String) r.get("code"))) {
                Db.exec(c, "begin mm_rights.drop_user_role(?, ?); end;", username, r.get("code"));
            }
        }
    }
}

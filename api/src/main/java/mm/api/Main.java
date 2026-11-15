package mm.api;

import com.sun.net.httpserver.HttpServer;

import java.net.InetSocketAddress;
import java.util.concurrent.Executors;

/**
 * mm-api: the REST service of the mini market. Its settings come from the environment (no password in
 * a file or in an argument):
 *
 * <pre>
 *   MM_API_BIND      the address it listens on (127.0.0.1: only this computer, until the login)
 *   MM_API_PORT      its port (8090)
 *   MM_DB_URL        the database (jdbc:oracle:thin:/@MM_DB: the alias of the wallet)
 *   MM_TNS_ADMIN     the folder of tnsnames.ora and sqlnet.ora (the domain of the Forms on Windows)
 *   MM_WALLET        the folder of the wallet (MM_TNS_ADMIN\forms_wallet)
 *   MM_DB_USER, MM_DB_PASSWORD   without a wallet (a test database): user and password
 * </pre>
 */
public final class Main {
    private Main() {
    }

    public static void main(String[] args) throws Exception {
        String bind = env("MM_API_BIND", "127.0.0.1");
        int port = Integer.parseInt(env("MM_API_PORT", "8090"));
        Db db = Db.fromEnvironment();
        HttpServer server = HttpServer.create(new InetSocketAddress(bind, port), 64);
        new Api(db).register(server);
        server.setExecutor(Executors.newFixedThreadPool(8));
        server.start();
        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            server.stop(1);
            db.close();
        }));
        System.out.println("== mm-api on http://" + bind + ":" + port + "/api/health");
    }

    static String env(String name, String fallback) {
        String v = System.getenv(name);
        return v == null || v.isBlank() ? fallback : v;
    }
}

# mm-api

Η υπηρεσία REST του mini market: Java 17 ή νεότερη, με τον `HttpServer` του JDK και JDBC (ojdbc11, UCP, το wallet). Οδηγίες: [docs/ODIGIES_REST.md](../docs/ODIGIES_REST.md).

```
powershell -ExecutionPolicy Bypass -File run_api.ps1   (Windows: χτίζει με το mvnw.cmd αν λείπει το jar, και ξεκινά με το wallet MM_DB)
mvnw.cmd -q -B package                                 (μόνο το jar: target\mm-api.jar)
```

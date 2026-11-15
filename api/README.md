# mm-api

Η υπηρεσία REST του mini market: Java 17 ή νεότερη, με τον `HttpServer` του JDK και JDBC (ojdbc11, UCP, το wallet). Οδηγίες: [docs/ODIGIES_REST.md](../docs/ODIGIES_REST.md).

```
mvn -q -B package                                   (target/mm-api.jar)
powershell -ExecutionPolicy Bypass -File run_api.ps1  (Windows, με το wallet MM_DB)
```

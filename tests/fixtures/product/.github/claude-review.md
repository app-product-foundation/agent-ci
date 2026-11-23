# Claude review extras for the example product

Text before the first section is ignored.

## code

Check that every new command handler is idempotent on `clientRequestId`.

## security

Treat any query that is not filtered by `accountId` as an IDOR.

## scope

Review only `src/` and `infra/`; ignore `docs/`.

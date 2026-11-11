# Ledger API — synthetic Understory fixture

This is inert example source for testing repository understanding. It is not a
live GitHub project. Understory reads this source and does not execute it.

## Purpose and architecture

The Ledger API accepts transfer requests. `app/api.py` is the request boundary.
It delegates payload checks to `app/validation.py` before calling
`TransferService` in `app/service.py`. The service writes through `LedgerStore`
in `app/storage.py`. The store keeps entries in memory for this fixture.

## Validation

A request requires a nonempty `account_id` and a positive integer `amount` in
cents. Booleans are rejected as amounts. Invalid requests raise
`ValidationError`; no database or external payment gateway is contacted.

## Tests and limitations

The test files describe validation and transfer behavior. Finding these files
does not establish that tests have been run. This fixture has no authentication,
production database, Kubernetes deployment, billing provider, or encryption key.

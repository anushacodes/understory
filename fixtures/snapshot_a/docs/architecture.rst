Ledger architecture
===================

Request flow
------------

The request boundary validates a transfer payload, then delegates to the service.
The service receives a store as a constructor dependency. The store appends a
copy of each transfer and returns a monotonically numbered receipt identifier.

Persistence limits
------------------

Entries live only in process memory. Restarting the fixture would lose them.
There is no claim of durable financial processing or external payment handling.

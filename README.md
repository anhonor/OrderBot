## `🛍️ Telegram Order Bot`
### `ADDING PRODUCTS`
`import asyncio` `from extensions.database import database`
```
Async: await database.__add_product__(1, 'Example + Balance', './database/products/example-plus-balance.txt', 1.25)
Synchronous: asyncio.run(database.__add_product__(2, 'Example + CC', './database/products/example-plus-cc.txt', 1.25))
```
In order to create a product without any issues, use the following format: `(Product ID, Product Name, File Path, Product Price Per)`

### `READ`
The bot is not completed, and won't be for a long time, or until I feel like completing. There's a few errors within the bot, and it's pretty identifiable. 
1. The **Cashapp API Wrapper** is buggy, and has errors with timestamps, and timezones.
2. There are often runtime errors when a user attempts to purchase credits with cashapp, as it's the only supported payment at the moment.
3. Some commands aren't finished.

### `COMING SOON`
- [ ] `Cashapp API Wrapper Fix`
- [ ] `Cryptocurrency Payment Support`
- [ ] `Ordering Fix`
- [ ] `Product Creation via Bot`

import aiosqlite
import asyncio
import time

class DatabaseError(Exception):
    pass

class DatabaseFileNotFound(Exception):
    pass

class Database:
    @staticmethod
    def __make_neat__(file_path: str) -> str:
        return file_path if file_path[:2] == './' else './' + file_path

    def __init__(self, file_path: str) -> None:
        self.file_path = Database.__make_neat__(file_path)

    async def __init_db__(self):
        try:
          async with aiosqlite.connect(self.file_path) as d:
                await d.execute('''
                    CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY,
                        balance REAL NOT NULL,
                        cart TEXT NOT NULL,
                        paginatorPage INTEGER NOT NULL
                    )
                ''')
                await d.execute('''
                    CREATE TABLE IF NOT EXISTS orders (
                        id INTEGER NOT NULL,
                        orderId TEXT PRIMARY KEY,
                        orderPrice NUMERIC NOT NULL,
                        paymentMethod TEXT NOT NULL
                    )
                ''')
                await d.execute('''
                    CREATE TABLE IF NOT EXISTS products (
                        productId INTEGER PRIMARY KEY,
                        productSlug TEXT NOT NULL,
                        productFilePath TEXT NOT NULL,
                        productPricePer NUMERIC NOT NULL
                    )
                ''')
                await d.execute('''
                    CREATE TABLE IF NOT EXISTS receipts (
                        receiptId TEXT NOT NULL
                    )
                ''')
                await d.execute('''
                    CREATE TABLE IF NOT EXISTS blacklisted (
                        id INTEGER NOT NULL
                    )
                ''')
                await d.commit()
        except Exception as E:
            raise DatabaseError('{}: {}'.format(type(E), str(E)))
        
    async def __update_user__(self, user_id: int, new_balance: float = None, new_cart: str = None, new_page: int = None) -> None:
        try:
            async with aiosqlite.connect(self.file_path) as database:
                update_query = 'UPDATE users SET '
                values = []
                if new_balance is not None: update_query += 'balance=?, '; values.append(new_balance)
                if new_cart is not None: update_query += 'cart=?, '; values.append(new_cart)
                if new_page is not None: update_query += 'paginatorPage=?, '; values.append(new_page)
                update_query = update_query.rstrip(', ')
                update_query += ' WHERE id=?'
                values.append(user_id)
                await database.execute(update_query, tuple(values))
                await database.commit()
        except Exception as E:
            raise DatabaseError('{}: {}'.format(type(E), str(E)))
            
    async def __update_product__(self, product_id: int, new_slug: str = None, new_file_path: str = None, new_price_per: float = None) -> None:
        try:
            async with aiosqlite.connect(self.file_path) as database:
                update_query = 'UPDATE products SET '
                values = []
                if new_slug is not None:
                    update_query += 'productSlug=?, '
                    values.append(new_slug)
                if new_file_path is not None:
                    update_query += 'productFilePath=?, '
                    values.append(new_file_path)
                if new_price_per is not None:
                    update_query += 'productPricePer=?, '
                    values.append(new_price_per)
                update_query = update_query.rstrip(', ')
                update_query += ' WHERE productId=?'
                values.append(product_id)
                await database.execute(update_query, tuple(values))
                await database.commit()
        except Exception as E:
            raise DatabaseError('{}: {}'.format(type(E), str(E)))
        
    async def __fetch_user__(self, user_id: int) -> tuple | None:
        try:
            async with aiosqlite.connect(self.file_path) as database:
                async with database.execute('SELECT balance, cart, paginatorPage FROM users WHERE id=?', (user_id,)) as cursor:
                    return await cursor.fetchone()  # returns (balance, cart, paginator_page) or None
        except Exception as E:
            raise DatabaseError('{}: {}'.format(type(E), str(E)))

    async def __fetch_order__(self, order_id: str) -> tuple | None:
        try:
            async with aiosqlite.connect(self.file_path) as database:
                async with database.execute(
                        'SELECT id, orderId, orderPrice, paymentMethod FROM orders WHERE orderId=?',
                        (order_id,)) as cursor:
                    return await cursor.fetchone()  # returns (id, order_id, order_price, payment_method) or None
        except Exception as E:
            raise DatabaseError('{}: {}'.format(type(E), str(E)))

    async def __fetch_product__(self, product_id: int) -> tuple | None:
        try:
            async with aiosqlite.connect(self.file_path) as database:
                async with database.execute(
                        'SELECT productSlug, productFilePath, productPricePer FROM products WHERE productId=?', (product_id,)) as cursor:
                    return await cursor.fetchone()  # returns (product_slug, product_file_path, product_price_per) or None
        except Exception as E:
            raise DatabaseError('{}: {}'.format(type(E), str(E)))
        
    async def __fetch_receipt__(self, user_id: int) -> tuple | None:
        try:
            async with aiosqlite.connect(self.file_path) as database:
                async with database.execute('SELECT receiptId FROM receipts WHERE receiptId=?', (user_id,)) as cursor:
                    return await cursor.fetchone()  # returns (id) or None
        except Exception as E:
            raise DatabaseError('{}: {}'.format(type(E), str(E)))
        
    async def __fetch_all_products__(self) -> list:
        try:
            async with aiosqlite.connect(self.file_path) as database:
                async with database.execute('SELECT productId, productSlug, productFilePath, productPricePer FROM products') as cursor:
                    return await cursor.fetchall()  # returns [(product_id, product_slug, product_file_path, product_price_per), ...]
        except Exception as E:
            raise DatabaseError('{}: {}'.format(type(E), str(E)))
        
    async def __fetch_all_orders__(self) -> list:
        try:
            async with aiosqlite.connect(self.file_path) as database:
                async with database.execute('SELECT id, orderId, orderPrice, paymentMethod FROM orders') as cursor:
                    return await cursor.fetchall()  # returns [(id, order_id, order_price, payment_method), ...]
        except Exception as E:
            raise DatabaseError('{}: {}'.format(type(E), str(E)))

    async def __fetch_all_users__(self) -> list:
        try:
            async with aiosqlite.connect(self.file_path) as database:
                async with database.execute('SELECT id, balance, cart, paginatorPage FROM users') as cursor:
                    return await cursor.fetchall()  # returns [(id, balance, cart), ...]
        except Exception as E:
            raise DatabaseError('{}: {}'.format(type(E), str(E)))

    async def __add_user__(self, user_id: int, amount: int = 0.00) -> bool:
        try:
            async with aiosqlite.connect(self.file_path) as database:
                async with database.execute('SELECT id FROM users WHERE id=? LIMIT 1', (user_id,)) as cursor:
                    last_entry = await cursor.fetchone()
                    if last_entry and last_entry[0] == user_id:
                        return False

                await database.execute('INSERT INTO users (id, balance, cart, paginatorPage) VALUES (?, ?, ?, ?)', (user_id, float(amount), '', 1))
                await database.commit()
                return True
        except Exception as E:
            raise DatabaseError('{}: {}'.format(type(E), str(E)))
        
    async def __add_receipt__(self, receipt: str) -> bool:
        try:
            async with aiosqlite.connect(self.file_path) as database:
                async with database.execute('SELECT receiptId FROM receipts WHERE receiptId=? LIMIT 1', (receipt,)) as cursor:
                    last_entry = await cursor.fetchone()
                    if last_entry and last_entry[0] == receipt:
                        return False

                await database.execute('INSERT INTO receipts (receiptId) VALUES (?)', (receipt, ))
                await database.commit()
                return True
        except Exception as E:
            raise DatabaseError('{}: {}'.format(type(E), str(E)))
        
    async def __add_blacklist__(self, id: int) -> bool:
        try:
            async with aiosqlite.connect(self.file_path) as database:
                async with database.execute('SELECT id FROM blacklisted WHERE id=? LIMIT 1', (id,)) as cursor:
                    last_entry = await cursor.fetchone()
                    if last_entry and last_entry[0] == id:
                        return False

                await database.execute('INSERT INTO blacklisted (id) VALUES (?)', (id, ))
                await database.commit()
                return True
        except Exception as E:
            raise DatabaseError('{}: {}'.format(type(E), str(E)))
        
    async def __remove_blacklist__(self, id: int) -> bool:
        try:
            async with aiosqlite.connect(self.file_path) as database:
                async with database.execute('SELECT id FROM blacklisted WHERE id=? LIMIT 1', (id,)) as cursor:
                    last_entry = await cursor.fetchone()
                    if not last_entry or last_entry[0] != id:
                        return False

                await database.execute('DELETE FROM blacklisted WHERE id=?', (id,))
                await database.commit()
                return True
        except Exception as E:
            raise DatabaseError('{}: {}'.format(type(E), str(E)))
            
    async def __remove_user__(self, id: int) -> bool:
        try:
            async with aiosqlite.connect(self.file_path) as database:
                async with database.execute('SELECT id FROM users WHERE id=? LIMIT 1', (id,)) as cursor:
                    last_entry = await cursor.fetchone()
                    if last_entry and last_entry[0] == id:
                        await database.execute('DELETE FROM users WHERE id=?', (id,))
                        await database.commit()
                        return True
                    else:
                        return False
        except Exception as E:
            raise DatabaseError('{}: {}'.format(type(E), str(E)))
        
    async def __is_blacklisted__(self, id: int) -> bool:
        try:
            async with aiosqlite.connect(self.file_path) as database:
                async with database.execute('SELECT id FROM blacklisted WHERE id=? LIMIT 1', (id,)) as cursor:
                    last_entry = await cursor.fetchone()
                    return bool(last_entry)
        except Exception as E:
            raise DatabaseError('{}: {}'.format(type(E), str(E)))
        
    async def __add_product__(self, product_id: int, product_slug: int, product_file_path: str, product_price_per: float | int) -> bool:
        try:
            async with aiosqlite.connect(self.file_path) as database:
                async with database.execute('SELECT productId FROM products WHERE productId=? LIMIT 1', (product_id,)) as cursor:
                    last_entry = await cursor.fetchone()
                    if last_entry and last_entry[0] == product_id:
                        return False

                await database.execute('INSERT INTO products (productId, productSlug, productFilePath, productPricePer) VALUES (?, ?, ?, ?)', (product_id, product_slug, product_file_path, product_price_per))
                await database.commit()
                return True
        except Exception as E:
            raise DatabaseError('{}: {}'.format(type(E), str(E)))
        
    async def __add_order__(self, id: int, order_id: str, order_price: int, payment_method: str) -> bool:
        try:
            async with aiosqlite.connect(self.file_path) as database:
                async with database.execute('SELECT orderId FROM orders where orderId=? LIMIT 1', (order_id,)) as cursor:
                    last_entry = await cursor.fetchone()
                    if last_entry and last_entry[0] == order_id:
                        return False

                await database.execute('INSERT INTO (id, orderId, orderPrice, paymentMethod) VALUES (?, ?, ?, ?)', (id, order_id, order_price, payment_method))
                await database.commit()
                return True
        except Exception as E:
            raise DatabaseError('{}: {}'.format(type(E), str(E)))
        
database = Database('./database/database.db')
for user in asyncio.run(database.__fetch_all_users__()):
    print(user)

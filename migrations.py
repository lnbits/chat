empty_dict: dict[str, str] = {}


async def m002_categories(db):
    """
    Initial categories table.
    """

    await db.execute(
        f"""
        CREATE TABLE chat.categories (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            name TEXT NOT NULL,
            paid BOOLEAN,
            tips BOOLEAN,
            chars INT,
            price_chars REAL,
            denomination TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT {db.timestamp_now},
            updated_at TIMESTAMP NOT NULL DEFAULT {db.timestamp_now}
        );
    """
    )


async def m003_client_data(db):
    """
    Initial client data table.
    """

    await db.execute(
        f"""
        CREATE TABLE chat.client_data (
            id TEXT PRIMARY KEY,
            categories_id TEXT NOT NULL,
            category TEXT NOT NULL,
            chat TEXT DEFAULT '{empty_dict}',
            created_at TIMESTAMP NOT NULL DEFAULT {db.timestamp_now},
            updated_at TIMESTAMP NOT NULL DEFAULT {db.timestamp_now}
        );
    """
    )


async def m004_categories_notify_fields(db):
    """
    Add wallet + notification fields to categories.
    """

    await db.execute(
        """
        ALTER TABLE chat.categories ADD COLUMN wallet TEXT;
        """
    )
    await db.execute(
        """
        ALTER TABLE chat.categories ADD COLUMN notify_telegram TEXT;
        """
    )
    await db.execute(
        """
        ALTER TABLE chat.categories ADD COLUMN notify_nostr TEXT;
        """
    )
    await db.execute(
        """
        ALTER TABLE chat.categories ADD COLUMN notify_email TEXT;
        """
    )


async def m005_chats(db):
    """
    Chat sessions table.
    """

    await db.execute(
        f"""
        CREATE TABLE chat.chats (
            id TEXT PRIMARY KEY,
            categories_id TEXT NOT NULL,
            title TEXT,
            resolved BOOLEAN DEFAULT 0,
            unread BOOLEAN DEFAULT 1,
            participants TEXT DEFAULT '[]',
            messages TEXT DEFAULT '[]',
            last_message_at TIMESTAMP,
            created_at TIMESTAMP NOT NULL DEFAULT {db.timestamp_now},
            updated_at TIMESTAMP NOT NULL DEFAULT {db.timestamp_now}
        );
    """
    )


async def m006_chat_payments(db):
    """
    Chat payments table for message gates and tips.
    """

    await db.execute(
        f"""
        CREATE TABLE chat.chat_payments (
            payment_hash TEXT PRIMARY KEY,
            chat_id TEXT NOT NULL,
            categories_id TEXT NOT NULL,
            sender_id TEXT NOT NULL,
            sender_name TEXT NOT NULL,
            sender_role TEXT NOT NULL,
            message TEXT NOT NULL,
            amount {db.big_int} NOT NULL,
            payment_type TEXT NOT NULL DEFAULT 'message',
            paid BOOLEAN DEFAULT 0,
            created_at TIMESTAMP NOT NULL DEFAULT {db.timestamp_now}
        );
    """
    )


async def m007_chats_public_url(db):
    """
    Add public URL to chat sessions.
    """

    await db.execute(
        """
        ALTER TABLE chat.chats ADD COLUMN public_url TEXT;
        """
    )

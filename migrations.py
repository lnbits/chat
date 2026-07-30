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
            resolved BOOLEAN DEFAULT FALSE,
            unread BOOLEAN DEFAULT TRUE,
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
            paid BOOLEAN DEFAULT FALSE,
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


async def m008_chat_lnurlp_balance(db):
    """
    Add lnurlp toggle to categories and balance to chats.
    """

    await db.execute(
        """
        ALTER TABLE chat.categories ADD COLUMN lnurlp BOOLEAN DEFAULT FALSE;
        """
    )
    await db.execute(
        f"""
        ALTER TABLE chat.chats ADD COLUMN balance {db.big_int} DEFAULT 0;
    """
    )


async def m009_chat_claims(db):
    """
    Add chat claim fields.
    """

    await db.execute(
        """
        ALTER TABLE chat.chats ADD COLUMN claimed_by_id TEXT;
        """
    )
    await db.execute(
        """
        ALTER TABLE chat.chats ADD COLUMN claimed_by_name TEXT;
        """
    )


async def m010_chat_claim_split(db):
    """
    Add claim split percentage to categories.
    """

    await db.execute(
        """
        ALTER TABLE chat.categories ADD COLUMN claim_split REAL DEFAULT 0;
        """
    )


async def m011_chat_guest_notifications(db):
    """
    Add guest notification fields and public note.
    """

    await db.execute(
        """
        ALTER TABLE chat.categories ADD COLUMN guest_notifications BOOLEAN DEFAULT FALSE;
        """
    )
    await db.execute(
        """
        ALTER TABLE chat.categories ADD COLUMN public_note TEXT;
        """
    )
    await db.execute(
        """
        ALTER TABLE chat.chats ADD COLUMN notify_email TEXT;
        """
    )
    await db.execute(
        """
        ALTER TABLE chat.chats ADD COLUMN notify_nostr TEXT;
        """
    )


async def m012_chat_schedules_seen_and_notification_jobs(db):
    """
    Add schedule/template fields, public seen fields, and notification jobs table.
    """

    await db.execute(
        """
        ALTER TABLE chat.categories ADD COLUMN schedule_enabled BOOLEAN DEFAULT FALSE;
        """
    )
    await db.execute(
        """
        ALTER TABLE chat.categories ADD COLUMN schedule_timezone TEXT DEFAULT 'Europe/London';
        """
    )
    await db.execute(
        """
        ALTER TABLE chat.categories ADD COLUMN schedule_days TEXT DEFAULT '0,1,2,3,4';
        """
    )
    await db.execute(
        """
        ALTER TABLE chat.categories ADD COLUMN schedule_start TEXT DEFAULT '09:00';
        """
    )
    await db.execute(
        """
        ALTER TABLE chat.categories ADD COLUMN schedule_end TEXT DEFAULT '17:00';
        """
    )
    await db.execute(
        """
        ALTER TABLE chat.categories ADD COLUMN admin_after_hours_subject TEXT;
        """
    )
    await db.execute(
        """
        ALTER TABLE chat.categories ADD COLUMN admin_after_hours_body TEXT;
        """
    )
    await db.execute(
        """
        ALTER TABLE chat.categories ADD COLUMN user_new_message_subject TEXT;
        """
    )
    await db.execute(
        """
        ALTER TABLE chat.categories ADD COLUMN user_new_message_body TEXT;
        """
    )
    await db.execute(
        """
        ALTER TABLE chat.chats ADD COLUMN public_last_seen_message_id TEXT;
        """
    )
    await db.execute(
        """
        ALTER TABLE chat.chats ADD COLUMN public_last_seen_at TIMESTAMP;
        """
    )
    await db.execute(
        f"""
        CREATE TABLE chat.notification_jobs (
            id TEXT PRIMARY KEY,
            chat_id TEXT NOT NULL,
            categories_id TEXT NOT NULL,
            job_type TEXT NOT NULL,
            message_id TEXT NOT NULL,
            due_at TIMESTAMP NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TIMESTAMP NOT NULL DEFAULT {db.timestamp_now},
            updated_at TIMESTAMP NOT NULL DEFAULT {db.timestamp_now}
        );
    """
    )


async def m013_categories_nostr_dm_type(db):
    """
    Add the Nostr direct-message type to category notifications.
    """

    await db.execute(
        """
        ALTER TABLE chat.categories
        ADD COLUMN notify_nostr_dm_type TEXT NOT NULL DEFAULT 'nip04';
        """
    )

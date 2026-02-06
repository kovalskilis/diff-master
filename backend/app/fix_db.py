"""Fix database: make user_id nullable in all tables for no-auth mode"""
import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

DATABASE_URL = "postgresql+asyncpg://legal_diff_user:dev123@localhost:5432/legal_diff"

async def fix_database():
    print("Connecting to database...")
    engine = create_async_engine(DATABASE_URL, echo=False)
    
    try:
        async with engine.begin() as conn:
            print("Connected! Updating tables...\n")
            
            # Make user_id nullable in all tables that have it
            tables_with_user_id = [
                "base_document",
                "snapshot", 
                "audit_log",
                "workspace_file",
                "edit_target",
                "patched_fragment",
                "excel_report"
            ]
            
            for table in tables_with_user_id:
                try:
                    # First check if column exists
                    result = await conn.execute(text(f"""
                        SELECT column_name FROM information_schema.columns 
                        WHERE table_name = '{table}' AND column_name = 'user_id'
                    """))
                    if result.fetchone():
                        await conn.execute(text(f"ALTER TABLE {table} ALTER COLUMN user_id DROP NOT NULL;"))
                        print(f"✓ {table}.user_id is now nullable")
                    else:
                        print(f"- {table}.user_id column doesn't exist (skipped)")
                except Exception as e:
                    print(f"✗ Error on {table}: {e}")
        
        print("\n✓ Database updated successfully!")
    except Exception as e:
        print(f"\n✗ Connection error: {e}")
        print("\nMake sure Docker is running and PostgreSQL container is up.")
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(fix_database())

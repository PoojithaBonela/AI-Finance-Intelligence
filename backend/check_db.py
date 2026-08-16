import os
import asyncio
from dotenv import load_dotenv

load_dotenv()

async def main():
    try:
        from supabase import create_client, Client
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_KEY")
        supabase: Client = create_client(url, key)
        
        # Check receipts
        try:
            res = supabase.table("receipts").select("*").limit(1).execute()
            print("Table 'receipts' EXISTS.")
        except Exception as e:
            print(f"Table 'receipts' DOES NOT EXIST (or error): {e}")

        # Check receipt_items
        try:
            res = supabase.table("receipt_items").select("*").limit(1).execute()
            print("Table 'receipt_items' EXISTS.")
        except Exception as e:
            print(f"Table 'receipt_items' DOES NOT EXIST (or error): {e}")

    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())

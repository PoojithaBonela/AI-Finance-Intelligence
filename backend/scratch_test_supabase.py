try:
    from supabase import create_client
    print("Supabase imported successfully")
except Exception as e:
    import traceback
    traceback.print_exc()

"""
Shared Supabase client using the service_role key (server-side only,
full access, bypasses RLS). Never expose this client or key to the frontend.
"""
from supabase import create_client, Client
from app.config import SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
import { createClient } from 'https://cdn.jsdelivr.net/npm/@supabase/supabase-js/+esm'

export const bd = createClient(
    'https://vdktsekpmokvdviqeyzh.supabase.co',
    'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZka3RzZWtwbW9rdmR2aXFleXpoIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzMxNTQwMjgsImV4cCI6MjA4ODczMDAyOH0.ePQhHxsusJ2y2Sp3H5vRy2cIqmULI3BtZO0KGSX4XTs'
)
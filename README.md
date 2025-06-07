# Plant Diagnosis System

A serverless API that uses AI to diagnose plant diseases from images stored in Supabase.

## Features

- Automatically processes plant images stored in Supabase
- Uses Google's Gemini AI to diagnose plant diseases
- Provides detailed diagnosis and treatment recommendations
- Updates diagnosis results back to Supabase database

## Deployment to Vercel

### Prerequisites

1. A Vercel account (sign up at [vercel.com](https://vercel.com))
2. Vercel CLI installed (optional for local development)
3. Supabase account with storage and database set up
4. Google Gemini API key

### Steps to Deploy

1. **Install Vercel CLI** (optional for local development):
   ```
   npm install -g vercel
   ```

2. **Login to Vercel**:
   ```
   vercel login
   ```

3. **Set up environment variables in Vercel**:
   
   You need to add the following environment variables in the Vercel dashboard:
   
   - `SUPABASE_URL`: Your Supabase project URL
   - `SUPABASE_SERVICE_ROLE_KEY`: Your Supabase service role key
   - `GEMINI_API_KEY`: Your Google Gemini API key
   
   To add these variables:
   
   a. Go to your project in the Vercel dashboard
   b. Click on "Settings" > "Environment Variables"
   c. Add each variable with its corresponding value
   d. Make sure to add them to Production, Preview, and Development environments

4. **Deploy to Vercel**:
   
   Option 1: Using Vercel CLI:
   ```
   vercel
   ```
   
   Option 2: Connect your GitHub repository to Vercel:
   
   a. Push your code to a GitHub repository
   b. In the Vercel dashboard, click "New Project"
   c. Import your GitHub repository
   d. Configure the project settings (the defaults should work)
   e. Click "Deploy"

5. **Verify Deployment**:
   
   Once deployed, you can test your API by sending a GET request to your Vercel deployment URL:
   ```
   curl https://your-vercel-url.vercel.app
   ```
   
   You should receive a JSON response indicating the API is running.

### API Endpoints

- `GET /`: Check if the API is running
- `POST /`: Process plant images
  - Body: `{"action": "process"}`
- `POST /`: Test connection to Supabase
  - Body: `{"action": "test_connection"}`

## Local Development

1. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

2. Create a `.env` file with your environment variables:
   ```
   SUPABASE_URL=your_supabase_url
   SUPABASE_SERVICE_ROLE_KEY=your_service_role_key
   GEMINI_API_KEY=your_gemini_api_key
   ```

3. Run the development server:
   ```
   vercel dev
   ```

## Notes

- The serverless function has a maximum execution time of 10 seconds in Vercel's free tier. If your processing takes longer, consider upgrading to a paid plan or implementing a queue system.
- Large image processing might exceed Vercel's memory limits. Consider resizing images before processing if needed. 
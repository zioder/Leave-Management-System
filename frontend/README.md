# Leave Management Frontend

React-based frontend application for the Leave Management System with chatbot interface and QuickSight analytics integration.

## Features

- **Chatbot Interface**: Natural language interaction with the leave management system
- **User/Admin Modes**: Toggle between user and admin modes
- **Employee Selection**: Select employee for user mode queries
- **QuickSight Analytics**: Embedded analytics dashboard for admin users
- **Real-time Updates**: Live chat interface with typing indicators

## Prerequisites

- Node.js 16+ and npm
- API Gateway endpoint URL (backend Lambda function)

## Installation

```bash
# Install dependencies
npm install

# Copy environment variables
cp .env.example .env

# Edit .env and set your API Gateway URL
# REACT_APP_API_URL=https://your-api-gateway-url.execute-api.region.amazonaws.com/prod
```

## Development

```bash
# Start development server
npm start
```

The app will open at http://localhost:3000

## Building for Production

```bash
# Build for production
npm run build

# The build folder will contain the production build
```

## Deployment

### Option 1: AWS Amplify Hosting

1. Connect your repository to AWS Amplify
2. Configure build settings:
   - Build command: `npm run build`
   - Output directory: `build`
3. Set environment variables in Amplify Console
4. Deploy

### Option 2: S3 + CloudFront

1. Build the application:
   ```bash
   npm run build
   ```

2. Upload to S3:
   ```bash
   aws s3 sync build/ s3://your-bucket-name --delete
   ```

3. Configure CloudFront distribution pointing to S3 bucket
4. Enable CloudFront caching for static assets

### Option 3: Docker

```dockerfile
FROM node:18-alpine as build
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/build /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

## Environment Variables

- `REACT_APP_API_URL`: API Gateway endpoint URL (required)
- `REACT_APP_QUICKSIGHT_DASHBOARD_URL`: QuickSight dashboard embedding URL (optional)
- `REACT_APP_AWS_REGION`: AWS region (optional)

## API Integration

The frontend communicates with the backend through the API Gateway endpoint. See `src/services/api.js` for API client implementation.

### Endpoints

- `POST /chat`: Send message to chatbot
- `GET /employees`: Get list of employees (for dropdown)

## QuickSight Integration

1. Set up QuickSight dashboard (see `QUICKSIGHT_SETUP.md`)
2. Enable dashboard embedding
3. Update `REACT_APP_QUICKSIGHT_DASHBOARD_URL` in `.env`
4. The dashboard will appear in admin mode

## Troubleshooting

### CORS Errors

If you encounter CORS errors, ensure your API Gateway has CORS enabled:
- Enable CORS in API Gateway console
- Add appropriate headers in Lambda response

### API Connection Issues

- Verify `REACT_APP_API_URL` is correct
- Check API Gateway logs
- Verify Lambda function is deployed and configured correctly

### QuickSight Dashboard Not Loading

- Verify dashboard URL is correct
- Check QuickSight embedding permissions
- Ensure dashboard is published and accessible

## Project Structure

```
frontend/
├── public/
│   └── index.html
├── src/
│   ├── components/
│   │   ├── ChatBot.js          # Chatbot interface
│   │   ├── ChatBot.css
│   │   ├── UserSelector.js     # User/admin mode selector
│   │   ├── UserSelector.css
│   │   ├── QuickSightDashboard.js  # Analytics dashboard
│   │   └── QuickSightDashboard.css
│   ├── services/
│   │   └── api.js              # API client
│   ├── App.js                  # Main app component
│   ├── App.css
│   ├── index.js                # Entry point
│   └── index.css
├── package.json
└── .env.example
```

## License

See main project LICENSE file.



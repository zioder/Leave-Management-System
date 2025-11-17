# Amazon QuickSight Setup Guide

This guide explains how to set up Amazon QuickSight analytics dashboards for the Leave Management System.

## Overview

QuickSight will provide visualizations for:
- Employee availability statistics
- Leave requests over time
- Department-wise leave distribution
- Leave balance analytics
- Real-time capacity monitoring (20-engineer rule)

## Prerequisites

1. AWS QuickSight subscription (Standard or Enterprise)
2. QuickSight permissions in your AWS account
3. Data sources configured (DynamoDB or Athena/S3)

## Step 1: Prepare Data Sources

### Option A: Use Athena (Recommended for Analytics)

1. **Set up AWS Glue Crawler** (if not already done):
   ```bash
   # Create Glue database
   aws glue create-database --database-input Name=leave_management
   
   # Create crawler (point to S3 bucket where Firehose writes data)
   aws glue create-crawler \
     --name leave-management-crawler \
     --role arn:aws:iam::YOUR_ACCOUNT:role/GlueServiceRole \
     --database-name leave_management \
     --targets "{\"S3Targets\":[{\"Path\":\"s3://your-bucket/leave-events/\"}]}"
   ```

2. **Run the crawler**:
   ```bash
   aws glue start-crawler --name leave-management-crawler
   ```

3. **Verify tables in Athena**:
   - Go to Athena Console
   - Select database: `leave_management`
   - Verify tables are created

### Option B: Use DynamoDB (For Real-time Data)

DynamoDB can be used directly, but for better performance with large datasets, consider:
- Exporting DynamoDB data to S3 periodically
- Using DynamoDB Streams → Lambda → S3 for incremental updates
- Querying via Athena on exported data

## Step 2: Create QuickSight Data Source

1. **Open QuickSight Console**
   - Go to https://quicksight.aws.amazon.com
   - Sign in to your account

2. **Create Data Source**:
   - Click "Manage data" → "New data set"
   - Choose data source type:
     - **Athena** (recommended for analytics)
     - **DynamoDB** (for real-time queries)
   - Configure connection:
     - For Athena: Select workgroup, database, and table
     - For DynamoDB: Select table and configure export settings

3. **Configure Permissions**:
   - Ensure QuickSight has access to your data source
   - Set up IAM roles if needed

## Step 3: Create Datasets

Create the following datasets:

### 1. Employee Availability Dataset
- **Source**: DynamoDB `EngineerAvailability` table or Athena view
- **Fields**:
  - `employee_id` (String)
  - `current_status` (String)
  - `on_leave_from` (Date)
  - `on_leave_to` (Date)
  - `updated_at` (Date)

### 2. Leave Quota Dataset
- **Source**: DynamoDB `LeaveQuota` table or Athena view
- **Fields**:
  - `employee_id` (String)
  - `annual_allowance` (Decimal)
  - `taken_ytd` (Decimal)
  - `available_days` (Decimal)
  - `carried_over` (Decimal)

### 3. Leave Requests Dataset
- **Source**: DynamoDB `LeaveRequests` table or Athena/S3 (from Firehose)
- **Fields**:
  - `request_id` (String)
  - `employee_id` (String)
  - `leave_type` (String)
  - `start_date` (Date)
  - `end_date` (Date)
  - `days` (Integer)
  - `status` (String)
  - `created_at` (Date)

### 4. Historical Events Dataset (from S3)
- **Source**: Athena table (from Glue Crawler)
- **Fields**: All fields from leave events stored in S3

## Step 4: Create Visualizations

### Visualization 1: Availability Overview
- **Type**: KPI or Number
- **Metrics**: 
  - Total Engineers
  - Available Engineers
  - On Leave
  - Availability Percentage

### Visualization 2: Leave Requests Timeline
- **Type**: Line Chart
- **X-axis**: Date (start_date)
- **Y-axis**: Count of requests
- **Color**: Status (APPROVED, DENIED, PENDING)

### Visualization 3: Department Distribution
- **Type**: Pie Chart or Bar Chart
- **Dimension**: Department
- **Metric**: Count of employees or leave days

### Visualization 4: Leave Balance Distribution
- **Type**: Histogram
- **Dimension**: Available days
- **Show**: Distribution of leave balances across employees

### Visualization 5: Capacity Monitor
- **Type**: Gauge
- **Metric**: Available engineers
- **Thresholds**: 
  - Green: >= 20
  - Yellow: 15-19
  - Red: < 15

### Visualization 6: Leave Requests by Type
- **Type**: Stacked Bar Chart
- **X-axis**: Leave type
- **Y-axis**: Count
- **Stack**: Status

## Step 5: Create Dashboard

1. **Create New Dashboard**:
   - Click "Dashboards" → "New dashboard"
   - Name: "Leave Management Analytics"

2. **Add Visualizations**:
   - Add all visualizations created in Step 4
   - Arrange them in a logical layout

3. **Configure Filters**:
   - Add date range filter
   - Add employee filter (for admin view)
   - Add department filter

4. **Set Refresh Schedule** (if using SPICE):
   - Configure automatic data refresh
   - For real-time data, use DIRECT_QUERY mode

## Step 6: Enable Dashboard Embedding

1. **Configure Embedding**:
   - Go to Dashboard settings
   - Enable "Embedding"
   - Generate embedding URL

2. **Set Up IAM Policy**:
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Action": [
           "quicksight:GetDashboardEmbedUrl"
         ],
         "Resource": "arn:aws:quicksight:*:*:dashboard/*"
       }
     ]
   }
   ```

3. **Update Frontend**:
   - Update `frontend/src/components/QuickSightDashboard.js`
   - Replace placeholder with actual dashboard embedding code
   - Use QuickSight JavaScript SDK or iframe embedding

## Step 7: Integrate with Frontend

### Option A: Iframe Embedding (Simplest)

Update `QuickSightDashboard.js`:

```javascript
import React, { useEffect, useRef } from 'react';

function QuickSightDashboard() {
  const containerRef = useRef(null);

  useEffect(() => {
    // Replace with your actual QuickSight dashboard URL
    const dashboardUrl = process.env.REACT_APP_QUICKSIGHT_DASHBOARD_URL;
    
    if (containerRef.current && dashboardUrl) {
      const iframe = document.createElement('iframe');
      iframe.src = dashboardUrl;
      iframe.width = '100%';
      iframe.height = '100%';
      iframe.frameBorder = '0';
      containerRef.current.innerHTML = '';
      containerRef.current.appendChild(iframe);
    }
  }, []);

  return <div className="quicksight-dashboard" ref={containerRef} />;
}
```

### Option B: QuickSight JavaScript SDK (Advanced)

```javascript
import { EmbeddingSDK } from '@aws-quicksight/embedding-sdk';

function QuickSightDashboard() {
  useEffect(() => {
    const embedDashboard = async () => {
      const dashboard = await EmbeddingSDK.createDashboard({
        url: process.env.REACT_APP_QUICKSIGHT_DASHBOARD_URL,
        container: '#dashboard-container',
        parameters: {
          // Add any dashboard parameters
        }
      });
      await dashboard.render();
    };
    
    embedDashboard();
  }, []);
  
  return <div id="dashboard-container" className="quicksight-dashboard" />;
}
```

## Step 8: Create Athena Views (Optional)

For better performance, create views that join multiple tables:

```sql
-- Create view for employee availability with quota
CREATE OR REPLACE VIEW employee_availability_view AS
SELECT 
    e.employee_id,
    e.current_status,
    e.on_leave_from,
    e.on_leave_to,
    q.annual_allowance,
    q.taken_ytd,
    q.available_days,
    q.carried_over
FROM engineer_availability e
LEFT JOIN leave_quota q ON e.employee_id = q.employee_id;
```

## Step 9: Set Up Automated Data Refresh

1. **For SPICE Datasets**:
   - Configure refresh schedule (hourly, daily, etc.)
   - Set up email notifications for refresh failures

2. **For DIRECT_QUERY**:
   - Data is always fresh (no refresh needed)
   - Consider caching for better performance

## Troubleshooting

### Issue: "Access Denied" when connecting to data source
**Solution**: 
- Check IAM permissions for QuickSight
- Verify data source permissions
- Ensure QuickSight service role has access

### Issue: Dashboard not loading in frontend
**Solution**:
- Verify embedding URL is correct
- Check CORS settings
- Verify authentication/authorization

### Issue: Data not updating
**Solution**:
- Check data source connection
- Verify refresh schedule (for SPICE)
- Check Athena query execution
- Verify DynamoDB export to S3 (if using)

## Best Practices

1. **Use SPICE for frequently accessed data**:
   - Improves performance
   - Reduces query costs
   - Set up appropriate refresh schedules

2. **Use DIRECT_QUERY for real-time data**:
   - Always up-to-date
   - Higher latency
   - May incur higher costs

3. **Optimize Datasets**:
   - Only include necessary fields
   - Use calculated fields for common metrics
   - Create joins in Athena rather than QuickSight

4. **Monitor Costs**:
   - QuickSight charges based on usage
   - Monitor SPICE storage
   - Optimize query patterns

## Additional Resources

- [QuickSight Documentation](https://docs.aws.amazon.com/quicksight/)
- [QuickSight Embedding SDK](https://github.com/aws-samples/amazon-quicksight-embedding-sdk)
- [QuickSight Best Practices](https://docs.aws.amazon.com/quicksight/latest/user/best-practices.html)

## Next Steps

1. Create the data sources in QuickSight Console
2. Build visualizations based on your requirements
3. Create and publish the dashboard
4. Enable embedding and integrate with frontend
5. Test the integration
6. Set up monitoring and alerts

For questions or issues, refer to the main [SETUP.md](SETUP.md) or [README.md](README.md).



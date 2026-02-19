-- ============================================================================
-- IC Orders Lead Time Extract
-- Source: RAE Data Lake (IFS + MOCHA combined)
-- Purpose: Extract order data for lead time forecasting
-- Author: HALIE / Redegades
-- Date: 2026-02-14
-- ============================================================================

-- This query pulls manufacturing order data from the data lake
-- for lead time analysis and Prophet forecasting

SELECT 
    -- Order Identifiers
    o.ORDER_NO,
    o.LINE_NO,
    o.PART_NO,
    
    -- Key Dates for Lead Time Calculation
    o.DATE_ENTERED,           -- When order was created
    o.NEED_DATE,              -- Customer requested date
    o.ORG_START_DATE,         -- Original planned start
    o.REVISED_START_DATE,     -- Actual/revised start
    o.COMPLETE_DATE,          -- Manufacturing complete
    o.REAL_SHIP_DATE,         -- Actual ship date
    
    -- Calculated Lead Time (days from entry to completion)
    DATEDIFF(day, o.DATE_ENTERED, o.COMPLETE_DATE) AS LEAD_TIME_DAYS,
    
    -- Additional Context
    o.DIVISION,
    o.ROWSTATE,
    
    -- Optional: Part category for filtering
    p.PART_DESCRIPTION,
    p.PART_CATEGORY
    
FROM DATA_LAKE.IC_ORDERS o
LEFT JOIN DATA_LAKE.PART_MASTER p 
    ON o.PART_NO = p.PART_NO

WHERE 
    -- Only completed orders (for historical accuracy)
    o.ROWSTATE = 'Closed'
    
    -- Valid date range (adjust as needed)
    AND o.DATE_ENTERED >= '2022-01-01'
    AND o.COMPLETE_DATE IS NOT NULL
    
    -- Exclude cancelled/invalid
    AND o.COMPLETE_DATE > o.DATE_ENTERED

ORDER BY 
    o.DATE_ENTERED ASC;


-- ============================================================================
-- ALTERNATIVE: Aggregated Weekly Summary
-- ============================================================================
-- Use this for direct Prophet input (pre-aggregated)

/*
SELECT 
    DATEADD(week, DATEDIFF(week, 0, DATE_ENTERED), 0) AS WEEK_START,
    PART_NO,
    COUNT(*) AS ORDER_COUNT,
    AVG(DATEDIFF(day, DATE_ENTERED, COMPLETE_DATE)) AS AVG_LEAD_TIME_DAYS,
    MIN(DATEDIFF(day, DATE_ENTERED, COMPLETE_DATE)) AS MIN_LEAD_TIME_DAYS,
    MAX(DATEDIFF(day, DATE_ENTERED, COMPLETE_DATE)) AS MAX_LEAD_TIME_DAYS,
    STDEV(DATEDIFF(day, DATE_ENTERED, COMPLETE_DATE)) AS STD_LEAD_TIME_DAYS

FROM DATA_LAKE.IC_ORDERS

WHERE 
    ROWSTATE = 'Closed'
    AND DATE_ENTERED >= '2022-01-01'
    AND COMPLETE_DATE IS NOT NULL
    AND COMPLETE_DATE > DATE_ENTERED

GROUP BY 
    DATEADD(week, DATEDIFF(week, 0, DATE_ENTERED), 0),
    PART_NO

ORDER BY 
    WEEK_START ASC,
    PART_NO;
*/


-- ============================================================================
-- NOTES
-- ============================================================================
-- 
-- Data Lake Tables Used:
--   - DATA_LAKE.IC_ORDERS: Combined IFS/MOCHA order data
--   - DATA_LAKE.PART_MASTER: Part information
--
-- Key Fields:
--   - DATE_ENTERED: Order creation date (start of lead time)
--   - COMPLETE_DATE: Manufacturing completion (end of lead time)
--   - LEAD_TIME_DAYS: Calculated difference
--
-- For forecasting, export results to CSV and use lead_time_forecaster.py
-- ============================================================================

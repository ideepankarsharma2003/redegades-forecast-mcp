-- ============================================================================
-- IC Orders Lead Time Extract
-- Source: RAE Data Lake (IFS + MOCHA combined)
-- Purpose: Extract order data for lead time forecasting
-- ============================================================================

SELECT
    o.ORDER_NO,
    o.LINE_NO,
    o.PART_NO,
    o.DATE_ENTERED,
    o.NEED_DATE,
    o.ORG_START_DATE,
    o.REVISED_START_DATE,
    o.COMPLETE_DATE,
    o.REAL_SHIP_DATE,
    DATEDIFF(day, o.DATE_ENTERED, o.COMPLETE_DATE) AS LEAD_TIME_DAYS,
    o.DIVISION,
    o.ROWSTATE,
    p.PART_DESCRIPTION,
    p.PART_CATEGORY
FROM DATA_LAKE.IC_ORDERS o
LEFT JOIN DATA_LAKE.PART_MASTER p
    ON o.PART_NO = p.PART_NO
WHERE
    o.ROWSTATE = 'Closed'
    AND o.DATE_ENTERED >= '2022-01-01'
    AND o.COMPLETE_DATE IS NOT NULL
    AND o.COMPLETE_DATE > o.DATE_ENTERED
ORDER BY
    o.DATE_ENTERED ASC;

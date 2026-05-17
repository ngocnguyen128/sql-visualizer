-- Báo cáo doanh thu hàng ngày
SELECT
    o.OrderDate,
    c.Name AS CustomerName,
    p.ProductName,
    oi.Quantity,
    p.Price * oi.Quantity AS Revenue
FROM Orders o
JOIN Customers c ON o.CustomerID = c.CustomerID
JOIN OrderItems oi ON o.OrderID = oi.OrderID
JOIN Products p ON oi.ProductID = p.ProductID
WHERE o.OrderDate >= CAST(GETDATE() AS DATE);

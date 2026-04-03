import React from "react";

const AnalyticsDashboard = ({ analytics }) => {
  if (!analytics) return null;

  return (
    <div className="max-w-7xl mx-auto px-6 py-6">
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <StatCard 
          label="Total Products"
          value={analytics.total_products}
          color="blue"
        />
        <StatCard 
          label="Listed"
          value={analytics.listed_products}
          color="green"
        />
        <StatCard 
          label="Sold"
          value={analytics.sold_products}
          color="yellow"
        />
        <StatCard 
          label="Total Sales"
          value={analytics.total_sales}
          color="purple"
        />
        <StatCard 
          label="Revenue"
          value={`$${analytics.total_revenue}`}
          color="emerald"
          gradient
        />
      </div>
    </div>
  );
};

const StatCard = ({ label, value, color, gradient }) => {
  const baseClass = "rounded-xl p-4 border border-white border-opacity-20";
  const colorClass = gradient 
    ? "bg-gradient-to-r from-green-500 to-emerald-500"
    : "bg-white bg-opacity-10 backdrop-blur-lg";
  
  const labelColorClass = gradient ? "text-green-100" : `text-${color}-200`;

  return (
    <div className={`${baseClass} ${colorClass}`}>
      <div className={`${labelColorClass} text-sm`}>{label}</div>
      <div className="text-white text-2xl font-bold mt-1">{value}</div>
    </div>
  );
};

export default AnalyticsDashboard;

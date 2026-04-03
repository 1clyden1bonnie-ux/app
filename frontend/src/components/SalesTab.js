import React from "react";

const SalesTab = ({ analytics }) => {
  const hasRevenue = analytics && 
    analytics.platform_revenue && 
    Object.keys(analytics.platform_revenue).length > 0;

  return (
    <div className="bg-white bg-opacity-10 backdrop-blur-lg rounded-2xl p-8 border border-white border-opacity-20">
      <h2 className="text-2xl font-bold text-white mb-6">💰 Sales History</h2>
      <p className="text-gray-300">
        Sales tracking coming soon. Products will automatically record sales when 
        purchased on Etsy, Shopify, or Gumroad.
      </p>
      
      {hasRevenue && (
        <RevenueByPlatform revenue={analytics.platform_revenue} />
      )}
    </div>
  );
};

const RevenueByPlatform = ({ revenue }) => (
  <div className="mt-6 space-y-3">
    <h3 className="text-lg font-bold text-white">Revenue by Platform</h3>
    {Object.entries(revenue).map(([platform, amount]) => (
      <PlatformRevenueCard 
        key={platform} 
        platform={platform} 
        amount={amount} 
      />
    ))}
  </div>
);

const PlatformRevenueCard = ({ platform, amount }) => (
  <div className="bg-white bg-opacity-10 rounded-lg p-4 border border-white border-opacity-20">
    <div className="flex justify-between">
      <span className="text-white font-medium capitalize">{platform}</span>
      <span className="text-green-300 font-bold">${amount.toFixed(2)}</span>
    </div>
  </div>
);

export default SalesTab;

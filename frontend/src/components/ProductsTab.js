import React from "react";

const ProductsTab = ({ products, onListProduct, onDeleteProduct }) => {
  return (
    <div className="bg-white bg-opacity-10 backdrop-blur-lg rounded-2xl p-8 border border-white border-opacity-20">
      <h2 className="text-2xl font-bold text-white mb-6">
        📦 Your Products ({products.length})
      </h2>
      
      <div className="space-y-4">
        {products.length === 0 ? (
          <EmptyState />
        ) : (
          products.map(product => (
            <ProductCard 
              key={product.id} 
              product={product}
              onListProduct={onListProduct}
              onDeleteProduct={onDeleteProduct}
            />
          ))
        )}
      </div>
    </div>
  );
};

const EmptyState = () => (
  <p className="text-gray-300 text-center py-8">
    No products yet. Generate some AI products!
  </p>
);

const ProductCard = ({ product, onListProduct, onDeleteProduct }) => {
  const getStatusColor = (status) => {
    if (status === "draft") return "text-yellow-200";
    if (status === "listed") return "text-green-200";
    return "text-purple-200";
  };

  return (
    <div className="bg-white bg-opacity-10 rounded-lg p-6 border border-white border-opacity-20">
      <div className="flex justify-between items-start">
        <ProductInfo product={product} getStatusColor={getStatusColor} />
        <ProductActions 
          product={product}
          onListProduct={onListProduct}
          onDeleteProduct={onDeleteProduct}
        />
      </div>
    </div>
  );
};

const ProductInfo = ({ product, getStatusColor }) => (
  <div className="flex-1">
    <h3 className="text-xl font-bold text-white">{product.name}</h3>
    <p className="text-gray-300 mt-2">{product.description}</p>
    <div className="flex gap-4 mt-3 text-sm">
      <span className="text-blue-200">Type: {product.product_type}</span>
      <span className="text-green-200">Price: ${product.price}</span>
      <span className={`font-medium ${getStatusColor(product.status)}`}>
        Status: {product.status}
      </span>
    </div>
    {product.listed_on && product.listed_on.length > 0 && (
      <PlatformBadges platforms={product.listed_on} />
    )}
  </div>
);

const PlatformBadges = ({ platforms }) => (
  <div className="mt-2">
    <span className="text-gray-300 text-sm">Listed on: </span>
    {platforms.map(platform => (
      <span 
        key={platform} 
        className="inline-block bg-blue-500 text-white text-xs px-2 py-1 rounded ml-2"
      >
        {platform}
      </span>
    ))}
  </div>
);

const ProductActions = ({ product, onListProduct, onDeleteProduct }) => (
  <div className="flex gap-2">
    {product.status === "draft" && (
      <button
        onClick={() => onListProduct(product.id)}
        className="bg-green-500 text-white px-4 py-2 rounded-lg hover:bg-green-600 transition-all text-sm font-medium"
      >
        List Product
      </button>
    )}
    <button
      onClick={() => onDeleteProduct(product.id)}
      className="bg-red-500 text-white px-4 py-2 rounded-lg hover:bg-red-600 transition-all text-sm font-medium"
    >
      Delete
    </button>
  </div>
);

export default ProductsTab;

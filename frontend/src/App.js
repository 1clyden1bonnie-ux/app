import { useState } from "react";
import "./App.css";
import AnalyticsDashboard from "./components/AnalyticsDashboard";
import GenerateTab from "./components/GenerateTab";
import ProductsTab from "./components/ProductsTab";
import SalesTab from "./components/SalesTab";
import { useProducts, useAnalytics, useProductGeneration } from "./hooks/useAppData";

function App() {
  const [activeTab, setActiveTab] = useState("generate");
  const [productType, setProductType] = useState("image");
  const [aiModel, setAiModel] = useState("openai");
  const [prompt, setPrompt] = useState("");

  // Custom hooks for data management
  const { products, fetchProducts, deleteProduct, listProduct } = useProducts();
  const { analytics, fetchAnalytics } = useAnalytics();
  const { loading, generatedProduct, generateProduct, setGeneratedProduct } = useProductGeneration(() => {
    fetchProducts();
    fetchAnalytics();
  });

  const handleGenerate = () => {
    generateProduct(productType, prompt, aiModel);
  };

  const handleListProduct = async (productId) => {
    const platforms = prompt("Enter platforms (comma-separated: etsy,shopify,gumroad):");
    if (!platforms) return;

    const price = prompt("Enter price:");
    if (!price) return;

    const success = await listProduct(
      productId,
      platforms.split(",").map(p => p.trim()),
      price
    );

    if (success) {
      alert("Product listed successfully!");
      fetchAnalytics();
    } else {
      alert("Listing failed");
    }
  };

  const handleDeleteProduct = async (productId) => {
    if (!window.confirm("Are you sure you want to delete this product?")) return;

    const success = await deleteProduct(productId);
    if (success) {
      alert("Product deleted!");
      fetchAnalytics();
    } else {
      alert("Delete failed");
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-purple-900 via-blue-900 to-indigo-900">
      <Header />
      <AnalyticsDashboard analytics={analytics} />
      <NavigationTabs activeTab={activeTab} setActiveTab={setActiveTab} />
      
      <div className="max-w-7xl mx-auto px-6 pb-12">
        {activeTab === "generate" && (
          <GenerateTab
            productType={productType}
            setProductType={setProductType}
            aiModel={aiModel}
            setAiModel={setAiModel}
            prompt={prompt}
            setPrompt={setPrompt}
            loading={loading}
            handleGenerate={handleGenerate}
            generatedProduct={generatedProduct}
          />
        )}

        {activeTab === "products" && (
          <ProductsTab
            products={products}
            onListProduct={handleListProduct}
            onDeleteProduct={handleDeleteProduct}
          />
        )}

        {activeTab === "sales" && (
          <SalesTab analytics={analytics} />
        )}
      </div>
    </div>
  );
}

const Header = () => (
  <div className="bg-black bg-opacity-30 backdrop-blur-lg border-b border-white border-opacity-10">
    <div className="max-w-7xl mx-auto px-6 py-4">
      <h1 className="text-3xl font-bold text-white">💰 AI Money Maker</h1>
      <p className="text-blue-200 mt-1">Generate AI Products & Sell Everywhere</p>
    </div>
  </div>
);

const NavigationTabs = ({ activeTab, setActiveTab }) => {
  const tabs = ["generate", "products", "sales"];

  return (
    <div className="max-w-7xl mx-auto px-6 py-4">
      <div className="flex gap-4">
        {tabs.map(tab => (
          <TabButton
            key={tab}
            tab={tab}
            isActive={activeTab === tab}
            onClick={() => setActiveTab(tab)}
          />
        ))}
      </div>
    </div>
  );
};

const TabButton = ({ tab, isActive, onClick }) => {
  const activeClass = "bg-white text-purple-900 shadow-lg";
  const inactiveClass = "bg-white bg-opacity-10 text-white hover:bg-opacity-20";

  return (
    <button
      onClick={onClick}
      className={`px-6 py-2 rounded-lg font-medium transition-all ${
        isActive ? activeClass : inactiveClass
      }`}
    >
      {tab.charAt(0).toUpperCase() + tab.slice(1)}
    </button>
  );
};

export default App;

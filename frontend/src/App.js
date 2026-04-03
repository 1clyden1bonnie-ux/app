import { useState, useEffect } from "react";
import axios from "axios";
import "./App.css";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

function App() {
  const [activeTab, setActiveTab] = useState("generate");
  const [products, setProducts] = useState([]);
  const [analytics, setAnalytics] = useState(null);
  const [loading, setLoading] = useState(false);
  
  // Generation form state
  const [productType, setProductType] = useState("image");
  const [aiModel, setAiModel] = useState("openai");
  const [prompt, setPrompt] = useState("");
  const [generatedProduct, setGeneratedProduct] = useState(null);

  useEffect(() => {
    fetchProducts();
    fetchAnalytics();
  }, []);

  const fetchProducts = async () => {
    try {
      const response = await axios.get(`${API}/products`);
      setProducts(response.data.products || []);
    } catch (error) {
      console.error("Error fetching products:", error);
    }
  };

  const fetchAnalytics = async () => {
    try {
      const response = await axios.get(`${API}/analytics`);
      setAnalytics(response.data);
    } catch (error) {
      console.error("Error fetching analytics:", error);
    }
  };

  const handleGenerate = async () => {
    if (!prompt.trim()) {
      alert("Please enter a prompt");
      return;
    }

    setLoading(true);
    setGeneratedProduct(null);

    try {
      const endpoint = productType === "image" ? "/generate/image" : "/generate/text";
      const response = await axios.post(`${API}${endpoint}`, {
        product_type: productType,
        prompt: prompt,
        ai_model: aiModel
      });

      setGeneratedProduct(response.data);
      fetchProducts();
      fetchAnalytics();
      alert("Product generated successfully!");
    } catch (error) {
      console.error("Generation error:", error);
      alert("Generation failed: " + (error.response?.data?.detail || error.message));
    } finally {
      setLoading(false);
    }
  };

  const handleListProduct = async (productId) => {
    const platforms = prompt("Enter platforms (comma-separated: etsy,shopify,gumroad):");
    if (!platforms) return;

    const price = prompt("Enter price:");
    if (!price) return;

    try {
      await axios.post(`${API}/list-product`, {
        product_id: productId,
        platforms: platforms.split(",").map(p => p.trim()),
        price: parseFloat(price)
      });
      
      alert("Product listed successfully!");
      fetchProducts();
      fetchAnalytics();
    } catch (error) {
      console.error("Listing error:", error);
      alert("Listing failed: " + (error.response?.data?.detail || error.message));
    }
  };

  const handleDeleteProduct = async (productId) => {
    if (!window.confirm("Are you sure you want to delete this product?")) return;

    try {
      await axios.delete(`${API}/products/${productId}`);
      alert("Product deleted!");
      fetchProducts();
      fetchAnalytics();
    } catch (error) {
      console.error("Delete error:", error);
      alert("Delete failed: " + (error.response?.data?.detail || error.message));
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-purple-900 via-blue-900 to-indigo-900">
      {/* Header */}
      <div className="bg-black bg-opacity-30 backdrop-blur-lg border-b border-white border-opacity-10">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <h1 className="text-3xl font-bold text-white">💰 AI Money Maker</h1>
          <p className="text-blue-200 mt-1">Generate AI Products & Sell Everywhere</p>
        </div>
      </div>

      {/* Analytics Bar */}
      {analytics && (
        <div className="max-w-7xl mx-auto px-6 py-6">
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            <div className="bg-white bg-opacity-10 backdrop-blur-lg rounded-xl p-4 border border-white border-opacity-20">
              <div className="text-blue-200 text-sm">Total Products</div>
              <div className="text-white text-2xl font-bold mt-1">{analytics.total_products}</div>
            </div>
            <div className="bg-white bg-opacity-10 backdrop-blur-lg rounded-xl p-4 border border-white border-opacity-20">
              <div className="text-green-200 text-sm">Listed</div>
              <div className="text-white text-2xl font-bold mt-1">{analytics.listed_products}</div>
            </div>
            <div className="bg-white bg-opacity-10 backdrop-blur-lg rounded-xl p-4 border border-white border-opacity-20">
              <div className="text-yellow-200 text-sm">Sold</div>
              <div className="text-white text-2xl font-bold mt-1">{analytics.sold_products}</div>
            </div>
            <div className="bg-white bg-opacity-10 backdrop-blur-lg rounded-xl p-4 border border-white border-opacity-20">
              <div className="text-purple-200 text-sm">Total Sales</div>
              <div className="text-white text-2xl font-bold mt-1">{analytics.total_sales}</div>
            </div>
            <div className="bg-gradient-to-r from-green-500 to-emerald-500 rounded-xl p-4 border border-white border-opacity-20">
              <div className="text-green-100 text-sm">Revenue</div>
              <div className="text-white text-2xl font-bold mt-1">${analytics.total_revenue}</div>
            </div>
          </div>
        </div>
      )}

      {/* Navigation Tabs */}
      <div className="max-w-7xl mx-auto px-6 py-4">
        <div className="flex gap-4">
          {["generate", "products", "sales"].map(tab => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`px-6 py-2 rounded-lg font-medium transition-all ${
                activeTab === tab
                  ? "bg-white text-purple-900 shadow-lg"
                  : "bg-white bg-opacity-10 text-white hover:bg-opacity-20"
              }`}
            >
              {tab.charAt(0).toUpperCase() + tab.slice(1)}
            </button>
          ))}
        </div>
      </div>

      {/* Main Content */}
      <div className="max-w-7xl mx-auto px-6 pb-12">
        {/* Generate Tab */}
        {activeTab === "generate" && (
          <div className="bg-white bg-opacity-10 backdrop-blur-lg rounded-2xl p-8 border border-white border-opacity-20">
            <h2 className="text-2xl font-bold text-white mb-6">🎨 Generate AI Product</h2>
            
            <div className="space-y-6">
              <div>
                <label className="block text-white mb-2 font-medium">Product Type</label>
                <select
                  value={productType}
                  onChange={(e) => setProductType(e.target.value)}
                  className="w-full px-4 py-3 rounded-lg bg-white bg-opacity-20 text-white border border-white border-opacity-30 focus:outline-none focus:ring-2 focus:ring-blue-400"
                >
                  <option value="image">🎨 AI Art / Images</option>
                  <option value="text">📝 Text Content / Ebooks</option>
                </select>
              </div>

              <div>
                <label className="block text-white mb-2 font-medium">AI Model</label>
                <select
                  value={aiModel}
                  onChange={(e) => setAiModel(e.target.value)}
                  className="w-full px-4 py-3 rounded-lg bg-white bg-opacity-20 text-white border border-white border-opacity-30 focus:outline-none focus:ring-2 focus:ring-blue-400"
                >
                  <option value="openai">OpenAI (GPT-5.2 / DALL-E)</option>
                  <option value="gemini">Google Gemini (Nano Banana)</option>
                </select>
              </div>

              <div>
                <label className="block text-white mb-2 font-medium">Prompt</label>
                <textarea
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  placeholder={productType === "image" 
                    ? "Describe the image you want to generate (e.g., 'A beautiful sunset over mountains with vibrant colors')" 
                    : "Describe the content to generate (e.g., 'Write a comprehensive guide about productivity hacks')"
                  }
                  className="w-full px-4 py-3 rounded-lg bg-white bg-opacity-20 text-white border border-white border-opacity-30 focus:outline-none focus:ring-2 focus:ring-blue-400 placeholder-gray-300"
                  rows="4"
                />
              </div>

              <button
                onClick={handleGenerate}
                disabled={loading}
                className="w-full bg-gradient-to-r from-blue-500 to-purple-600 text-white py-4 px-6 rounded-lg font-bold text-lg hover:from-blue-600 hover:to-purple-700 transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-lg"
              >
                {loading ? "Generating..." : "🚀 Generate Product"}
              </button>

              {generatedProduct && (
                <div className="mt-6 bg-green-500 bg-opacity-20 border border-green-400 rounded-lg p-4">
                  <p className="text-green-200 font-medium">✅ Product Generated Successfully!</p>
                  <p className="text-white text-sm mt-2">Product ID: {generatedProduct.product_id}</p>
                  <p className="text-gray-200 text-sm mt-1">Check the Products tab to view and list it.</p>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Products Tab */}
        {activeTab === "products" && (
          <div className="bg-white bg-opacity-10 backdrop-blur-lg rounded-2xl p-8 border border-white border-opacity-20">
            <h2 className="text-2xl font-bold text-white mb-6">📦 Your Products ({products.length})</h2>
            
            <div className="space-y-4">
              {products.length === 0 ? (
                <p className="text-gray-300 text-center py-8">No products yet. Generate some AI products!</p>
              ) : (
                products.map(product => (
                  <div key={product.id} className="bg-white bg-opacity-10 rounded-lg p-6 border border-white border-opacity-20">
                    <div className="flex justify-between items-start">
                      <div className="flex-1">
                        <h3 className="text-xl font-bold text-white">{product.name}</h3>
                        <p className="text-gray-300 mt-2">{product.description}</p>
                        <div className="flex gap-4 mt-3 text-sm">
                          <span className="text-blue-200">Type: {product.product_type}</span>
                          <span className="text-green-200">Price: ${product.price}</span>
                          <span className={`font-medium ${
                            product.status === "draft" ? "text-yellow-200" :
                            product.status === "listed" ? "text-green-200" :
                            "text-purple-200"
                          }`}>
                            Status: {product.status}
                          </span>
                        </div>
                        {product.listed_on && product.listed_on.length > 0 && (
                          <div className="mt-2">
                            <span className="text-gray-300 text-sm">Listed on: </span>
                            {product.listed_on.map(platform => (
                              <span key={platform} className="inline-block bg-blue-500 text-white text-xs px-2 py-1 rounded ml-2">
                                {platform}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                      <div className="flex gap-2">
                        {product.status === "draft" && (
                          <button
                            onClick={() => handleListProduct(product.id)}
                            className="bg-green-500 text-white px-4 py-2 rounded-lg hover:bg-green-600 transition-all text-sm font-medium"
                          >
                            List Product
                          </button>
                        )}
                        <button
                          onClick={() => handleDeleteProduct(product.id)}
                          className="bg-red-500 text-white px-4 py-2 rounded-lg hover:bg-red-600 transition-all text-sm font-medium"
                        >
                          Delete
                        </button>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        )}

        {/* Sales Tab */}
        {activeTab === "sales" && (
          <div className="bg-white bg-opacity-10 backdrop-blur-lg rounded-2xl p-8 border border-white border-opacity-20">
            <h2 className="text-2xl font-bold text-white mb-6">💰 Sales History</h2>
            <p className="text-gray-300">Sales tracking coming soon. Products will automatically record sales when purchased on Etsy, Shopify, or Gumroad.</p>
            
            {analytics && analytics.platform_revenue && Object.keys(analytics.platform_revenue).length > 0 && (
              <div className="mt-6 space-y-3">
                <h3 className="text-lg font-bold text-white">Revenue by Platform</h3>
                {Object.entries(analytics.platform_revenue).map(([platform, revenue]) => (
                  <div key={platform} className="bg-white bg-opacity-10 rounded-lg p-4 border border-white border-opacity-20">
                    <div className="flex justify-between">
                      <span className="text-white font-medium capitalize">{platform}</span>
                      <span className="text-green-300 font-bold">${revenue.toFixed(2)}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default App;

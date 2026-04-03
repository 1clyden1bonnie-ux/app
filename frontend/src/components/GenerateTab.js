import React from "react";

const GenerateTab = ({ 
  productType, 
  setProductType, 
  aiModel, 
  setAiModel, 
  prompt, 
  setPrompt, 
  loading, 
  handleGenerate, 
  generatedProduct 
}) => {
  return (
    <div className="bg-white bg-opacity-10 backdrop-blur-lg rounded-2xl p-8 border border-white border-opacity-20">
      <h2 className="text-2xl font-bold text-white mb-6">🎨 Generate AI Product</h2>
      
      <div className="space-y-6">
        <SelectField
          label="Product Type"
          value={productType}
          onChange={setProductType}
          options={[
            { value: "image", label: "🎨 AI Art / Images" },
            { value: "text", label: "📝 Text Content / Ebooks" }
          ]}
        />

        <SelectField
          label="AI Model"
          value={aiModel}
          onChange={setAiModel}
          options={[
            { value: "openai", label: "OpenAI (GPT-5.2 / DALL-E)" },
            { value: "gemini", label: "Google Gemini (Nano Banana)" }
          ]}
        />

        <TextAreaField
          label="Prompt"
          value={prompt}
          onChange={setPrompt}
          placeholder={
            productType === "image" 
              ? "Describe the image you want to generate (e.g., 'A beautiful sunset over mountains with vibrant colors')" 
              : "Describe the content to generate (e.g., 'Write a comprehensive guide about productivity hacks')"
          }
        />

        <button
          onClick={handleGenerate}
          disabled={loading}
          className="w-full bg-gradient-to-r from-blue-500 to-purple-600 text-white py-4 px-6 rounded-lg font-bold text-lg hover:from-blue-600 hover:to-purple-700 transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-lg"
        >
          {loading ? "Generating..." : "🚀 Generate Product"}
        </button>

        {generatedProduct && (
          <SuccessMessage productId={generatedProduct.product_id} />
        )}
      </div>
    </div>
  );
};

const SelectField = ({ label, value, onChange, options }) => (
  <div>
    <label className="block text-white mb-2 font-medium">{label}</label>
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="w-full px-4 py-3 rounded-lg bg-white bg-opacity-20 text-white border border-white border-opacity-30 focus:outline-none focus:ring-2 focus:ring-blue-400"
    >
      {options.map(opt => (
        <option key={opt.value} value={opt.value}>{opt.label}</option>
      ))}
    </select>
  </div>
);

const TextAreaField = ({ label, value, onChange, placeholder }) => (
  <div>
    <label className="block text-white mb-2 font-medium">{label}</label>
    <textarea
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      className="w-full px-4 py-3 rounded-lg bg-white bg-opacity-20 text-white border border-white border-opacity-30 focus:outline-none focus:ring-2 focus:ring-blue-400 placeholder-gray-300"
      rows="4"
    />
  </div>
);

const SuccessMessage = ({ productId }) => (
  <div className="mt-6 bg-green-500 bg-opacity-20 border border-green-400 rounded-lg p-4">
    <p className="text-green-200 font-medium">✅ Product Generated Successfully!</p>
    <p className="text-white text-sm mt-2">Product ID: {productId}</p>
    <p className="text-gray-200 text-sm mt-1">Check the Products tab to view and list it.</p>
  </div>
);

export default GenerateTab;

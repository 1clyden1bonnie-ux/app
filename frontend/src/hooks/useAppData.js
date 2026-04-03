import { useState, useEffect, useCallback } from "react";
import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export const useProducts = () => {
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(false);

  const fetchProducts = useCallback(async () => {
    try {
      const response = await axios.get(`${API}/products`);
      setProducts(response.data.products || []);
    } catch (error) {
      console.error("Error fetching products:", error);
    }
  }, []);

  useEffect(() => {
    fetchProducts();
  }, [fetchProducts]);

  const deleteProduct = useCallback(async (productId) => {
    try {
      await axios.delete(`${API}/products/${productId}`);
      await fetchProducts();
      return true;
    } catch (error) {
      console.error("Delete error:", error);
      return false;
    }
  }, [fetchProducts]);

  const listProduct = useCallback(async (productId, platforms, price) => {
    try {
      await axios.post(`${API}/list-product`, {
        product_id: productId,
        platforms: platforms,
        price: parseFloat(price)
      });
      await fetchProducts();
      return true;
    } catch (error) {
      console.error("Listing error:", error);
      return false;
    }
  }, [fetchProducts]);

  return {
    products,
    loading,
    fetchProducts,
    deleteProduct,
    listProduct
  };
};

export const useAnalytics = () => {
  const [analytics, setAnalytics] = useState(null);

  const fetchAnalytics = useCallback(async () => {
    try {
      const response = await axios.get(`${API}/analytics`);
      setAnalytics(response.data);
    } catch (error) {
      console.error("Error fetching analytics:", error);
    }
  }, []);

  useEffect(() => {
    fetchAnalytics();
  }, [fetchAnalytics]);

  return { analytics, fetchAnalytics };
};

export const useProductGeneration = (onSuccess) => {
  const [loading, setLoading] = useState(false);
  const [generatedProduct, setGeneratedProduct] = useState(null);

  const generateProduct = useCallback(async (productType, prompt, aiModel) => {
    if (!prompt.trim()) {
      alert("Please enter a prompt");
      return false;
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
      if (onSuccess) onSuccess();
      alert("Product generated successfully!");
      return true;
    } catch (error) {
      console.error("Generation error:", error);
      alert("Generation failed: " + (error.response?.data?.detail || error.message));
      return false;
    } finally {
      setLoading(false);
    }
  }, [onSuccess]);

  return {
    loading,
    generatedProduct,
    generateProduct,
    setGeneratedProduct
  };
};

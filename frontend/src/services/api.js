import axios from 'axios';

// Configure API base URL
// In production, this should point to your API Gateway endpoint
const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:3001';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

/**
 * Send a message to the chatbot
 * @param {string} message - User's message
 * @param {string|null} employeeId - Selected employee ID (for user mode)
 * @param {boolean} isAdmin - Whether user is in admin mode
 * @returns {Promise} API response
 */
export const sendMessage = async (message, employeeId = null, isAdmin = false) => {
  try {
    const response = await api.post('/chat', {
      message,
      employee_id: employeeId,
      is_admin: isAdmin,
    });
    return response.data;
  } catch (error) {
    console.error('API Error:', error);
    throw error;
  }
};

/**
 * Get list of employees
 * @returns {Promise} List of employees
 */
export const getEmployees = async () => {
  try {
    const response = await api.get('/employees');
    return response.data;
  } catch (error) {
    console.error('API Error:', error);
    throw error;
  }
};

export default api;



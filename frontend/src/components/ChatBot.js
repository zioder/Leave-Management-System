import React, { useState, useRef, useEffect } from 'react';
import './ChatBot.css';
import { sendMessage } from '../services/api';

function ChatBot({ isAdmin, employeeId }) {
  const [messages, setMessages] = useState([
    {
      text: isAdmin 
        ? "Welcome, Admin! You can view all employees, check availability, and manage leave requests."
        : employeeId 
          ? `Hello! How can I help you with your leave management?`
          : "Please select an employee to start chatting.",
      sender: 'bot',
      timestamp: new Date(),
    }
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef(null);
  // Track the employee ID from conversation context (for follow-up questions)
  const [contextEmployeeId, setContextEmployeeId] = useState(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    // Reset conversation when mode or employee changes
    setMessages([{
      text: isAdmin 
        ? "Welcome, Admin! You can view all employees, check availability, and manage leave requests."
        : employeeId 
          ? `Hello! How can I help you with your leave management?`
          : "Please select an employee to start chatting.",
      sender: 'bot',
      timestamp: new Date(),
    }]);
    setContextEmployeeId(null);
  }, [isAdmin, employeeId]);

  const handleSend = async (e) => {
    e.preventDefault();
    
    if (!input.trim()) return;
    
    // Don't allow sending if user mode and no employee selected
    if (!isAdmin && !employeeId) {
      setMessages(prev => [...prev, {
        text: "Please select an employee first.",
        sender: 'bot',
        timestamp: new Date(),
      }]);
      return;
    }

    const userMessage = {
      text: input,
      sender: 'user',
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);

    try {
      // Use context ID if available (supports follow-up questions), otherwise fallback to selected employee
      const activeEmployeeId = isAdmin ? (contextEmployeeId || employeeId) : employeeId;
      const response = await sendMessage(input, activeEmployeeId, isAdmin);
      
      // Update context if we're in admin mode and an employee was identified
      if (isAdmin && response.command && response.command.employee_id) {
        setContextEmployeeId(response.command.employee_id);
      }

      const botMessage = {
        text: response.message || response.error || 'Sorry, I could not process your request.',
        sender: 'bot',
        timestamp: new Date(),
      };
      setMessages(prev => [...prev, botMessage]);
    } catch (error) {
      console.error('Error sending message:', error);
      setMessages(prev => [...prev, {
        text: 'Sorry, there was an error processing your request. Please try again.',
        sender: 'bot',
        timestamp: new Date(),
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="chatbot">
      <div className="chatbot-header">
        <h2>Chat Assistant</h2>
        <span className="chatbot-status">
          {isLoading ? 'Thinking...' : 'Online'}
        </span>
      </div>
      
      <div className="chatbot-messages">
        {messages.map((msg, index) => (
          <div key={index} className={`message ${msg.sender}`}>
            <div className="message-content">
              <p>{msg.text}</p>
              <span className="message-time">
                {msg.timestamp.toLocaleTimeString()}
              </span>
            </div>
          </div>
        ))}
        {isLoading && (
          <div className="message bot">
            <div className="message-content">
              <div className="typing-indicator">
                <span></span>
                <span></span>
                <span></span>
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <form className="chatbot-input" onSubmit={handleSend}>
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={isAdmin ? "Ask about employees, availability, or leave requests..." : "Ask about your leave balance or request time off..."}
          disabled={isLoading || (!isAdmin && !employeeId)}
        />
        <button type="submit" disabled={isLoading || (!isAdmin && !employeeId)}>
          Send
        </button>
      </form>
    </div>
  );
}

export default ChatBot;



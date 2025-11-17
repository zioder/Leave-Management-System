import React, { useState, useEffect } from 'react';
import './App.css';
import ChatBot from './components/ChatBot';
import UserSelector from './components/UserSelector';
import QuickSightDashboard from './components/QuickSightDashboard';
import { getEmployees } from './services/api';

function App() {
  const [isAdmin, setIsAdmin] = useState(false);
  const [selectedEmployee, setSelectedEmployee] = useState(null);
  const [employees, setEmployees] = useState([]);
  const [showAnalytics, setShowAnalytics] = useState(false);

  useEffect(() => {
    // Load employees for dropdown
    getEmployees()
      .then(data => setEmployees(data || []))
      .catch(err => console.error('Failed to load employees:', err));
  }, []);

  const handleModeChange = (admin) => {
    setIsAdmin(admin);
    if (!admin) {
      // Reset employee selection when switching to user mode
      setSelectedEmployee(null);
    }
  };

  const handleEmployeeChange = (employeeId) => {
    setSelectedEmployee(employeeId);
  };

  return (
    <div className="App">
      <header className="App-header">
        <h1>Leave Management System</h1>
        <UserSelector
          isAdmin={isAdmin}
          onModeChange={handleModeChange}
          employees={employees}
          selectedEmployee={selectedEmployee}
          onEmployeeChange={handleEmployeeChange}
        />
      </header>
      
      <main className="App-main">
        <div className="main-content">
          <div className="chat-container">
            <ChatBot
              isAdmin={isAdmin}
              employeeId={selectedEmployee}
            />
          </div>
          
          {isAdmin && (
            <div className="analytics-container">
              <button
                className="toggle-analytics"
                onClick={() => setShowAnalytics(!showAnalytics)}
              >
                {showAnalytics ? 'Hide' : 'Show'} Analytics Dashboard
              </button>
              {showAnalytics && <QuickSightDashboard />}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

export default App;



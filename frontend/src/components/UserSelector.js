import React from 'react';
import './UserSelector.css';

function UserSelector({ isAdmin, onModeChange, employees, selectedEmployee, onEmployeeChange }) {
  return (
    <div className="user-selector">
      <div className="mode-selector">
        <label>
          <input
            type="radio"
            name="mode"
            checked={!isAdmin}
            onChange={() => onModeChange(false)}
          />
          User Mode
        </label>
        <label>
          <input
            type="radio"
            name="mode"
            checked={isAdmin}
            onChange={() => onModeChange(true)}
          />
          Admin Mode
        </label>
      </div>

      {!isAdmin && (
        <div className="employee-selector">
          <label htmlFor="employee-select">Select Employee:</label>
          <select
            id="employee-select"
            value={selectedEmployee || ''}
            onChange={(e) => onEmployeeChange(e.target.value)}
            className="employee-dropdown"
          >
            <option value="">-- Select an employee --</option>
            {employees.map(emp => (
              <option key={emp.id} value={emp.id}>
                {emp.name} - {emp.department}
              </option>
            ))}
          </select>
        </div>
      )}

      {isAdmin && (
        <div className="admin-badge">
          <span>Admin Mode Active</span>
        </div>
      )}
    </div>
  );
}

export default UserSelector;



# Minimal React app (create‑react‑app style)

import React, { useState } from 'react';

function App() {
  const [item, setItem] = useState('');
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const fetchData = async () => {
    setError(null);
    setResult(null);
    try {
      const resp = await fetch(`http://localhost:5000/api/sazonalidade?item=${encodeURIComponent(item)}`);
      const data = await resp.json();
      if (resp.ok) setResult(data);
      else setError(data.error || 'Error');
    } catch (e) {
      setError(e.message);
    }
  };

  return (
    <div style={{ padding: '2rem', fontFamily: 'Arial, sans-serif' }}>
      <h1>Seasonal Price Analyzer</h1>
      <input
        placeholder="Item name (e.g., arroz)"
        value={item}
        onChange={e => setItem(e.target.value)}
        style={{ padding: '0.5rem', marginRight: '0.5rem' }}
      />
      <button onClick={fetchData}>Get Seasonality</button>
      {error && <p style={{ color: 'red' }}>{error}</p>}
      {result && (
        <pre style={{ background: '#f0f0f0', padding: '1rem', marginTop: '1rem' }}>
          {JSON.stringify(result, null, 2)}
        </pre>
      )}
    </div>
  );
}

export default App;

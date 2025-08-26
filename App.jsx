import React, { useState, useEffect, useRef } from 'react';

export default function App() {
  const [prompt, setPrompt] = useState('');
  const [responseData, setResponseData] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [connection, setConnection] = useState({ host: '', port: '', user: '', password: '', database: '' });
  const scrollRef = useRef(null);

  const handleSubmit = async () => {
    if (!prompt.trim()) {
      setError('Please enter a prompt before submitting.');
      return;
    }

    setLoading(true);
    setError('');
    setResponseData(null);

    try {
      const res = await fetch('http://localhost:8000/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt, connection }),
      });
      const result = await res.json();
      if (result.error) {
        setError(result.error);
      } else {
        setResponseData(result);
      }
    } catch (err) {
      setError('Failed to connect to server');
    }
    setLoading(false);
  };

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [responseData]);

  const handleClear = () => {
    setPrompt('');
    setResponseData(null);
    setError('');
  };

  const handleConnectionChange = (e) => {
    setConnection({ ...connection, [e.target.name]: e.target.value });
  };

  return (
    <div className="min-h-screen bg-gray-900 text-white flex flex-col items-center justify-center p-6">
      <div className="w-full max-w-4xl bg-gray-800 p-8 rounded-2xl shadow-2xl">
        <h1 className="text-4xl font-extrabold mb-8 text-center text-green-400 tracking-wide">
          Talk To DB
        </h1>

        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-5 gap-6 mb-8">
          {['host', 'port', 'user', 'password', 'database'].map((field) => (
            <input
              key={field}
              name={field}
              value={connection[field]}
              onChange={handleConnectionChange}
              placeholder={field.charAt(0).toUpperCase() + field.slice(1)}
              type={field === 'password' ? 'password' : 'text'}
              className="bg-gray-700 placeholder-gray-400 text-white px-4 py-3 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-400 transition"
              autoComplete="off"
            />
          ))}
        </div>

        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder="Type your SQL-related prompt here..."
          className="w-full h-48 p-6 mb-6 bg-gray-700 placeholder-gray-400 text-white rounded-2xl resize-none focus:outline-none focus:ring-4 focus:ring-green-400 font-mono text-lg shadow-inner transition"
        ></textarea>

        <div className="flex flex-col md:flex-row justify-center gap-6 mb-6">
          <button
            onClick={handleSubmit}
            disabled={loading}
            className="bg-green-500 hover:bg-green-600 disabled:bg-green-700 disabled:cursor-not-allowed text-white px-10 py-4 rounded-3xl font-semibold text-lg shadow-lg transition"
          >
            {loading ? 'Generating...' : 'Run Query'}
          </button>
          <button
            onClick={handleClear}
            className="bg-red-600 hover:bg-red-700 text-white px-10 py-4 rounded-3xl font-semibold text-lg shadow-lg transition"
          >
            Clear
          </button>
        </div>

        {error && (
          <p className="text-red-500 font-medium text-center mb-6 text-lg">
            ❌ {error}
          </p>
        )}

        {responseData && (
          <div
            ref={scrollRef}
            className="mt-8 w-full max-h-[40vh] overflow-auto scrollbar-thin scrollbar-thumb-green-500 scrollbar-track-gray-700"
          >
            <p className="font-semibold text-xl mb-3 text-green-400">Generated SQL:</p>
            <div className="relative bg-black text-green-400 p-6 rounded-xl font-mono text-sm shadow-lg whitespace-pre-wrap break-words overflow-x-auto mb-6 border border-green-500">
              {responseData.sql}
            </div>
            <div className="text-right mb-8">
              <button
                onClick={() => navigator.clipboard.writeText(responseData.sql)}
                className="bg-gray-700 hover:bg-gray-600 text-white text-xs px-4 py-2 rounded-xl shadow transition"
              >
                Copy
              </button>
            </div>

            <p className="font-semibold text-xl mb-3 text-green-400">Output:</p>
            <div className="overflow-x-auto border border-gray-700 rounded-lg shadow-inner bg-gray-900">
              <table className="min-w-full divide-y divide-gray-700 table-auto">
                <thead className="bg-gray-800">
                  <tr>
                    {Object.keys(responseData.data[0] || {}).map((key) => (
                      <th
                        key={key}
                        className="px-6 py-3 text-sm font-medium text-gray-300 border-b border-gray-600 text-center uppercase tracking-wide"
                      >
                        {key}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="bg-gray-900 divide-y divide-gray-700">
                  {responseData.data.map((row, rowIndex) => (
                    <tr
                      key={rowIndex}
                      className={rowIndex % 2 === 0 ? 'bg-gray-800' : 'bg-gray-900'}
                    >
                      {Object.values(row).map((value, colIndex) => (
                        <td
                          key={colIndex}
                          className="px-6 py-3 text-sm text-gray-200 border-b border-gray-700 text-center truncate max-w-xs"
                          title={value}
                        >
                          {value}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

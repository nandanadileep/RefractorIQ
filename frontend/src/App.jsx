import React, { useState, useEffect, useRef } from 'react';
import { Search, Github, AlertCircle, CheckCircle, TrendingUp, GitBranch, FileCode, Zap, Info, Package, TestTube, CopyCheck, Loader2, Share2, FileText, BrainCircuit } from 'lucide-react';
import { ReactFlowProvider } from 'reactflow';
import DependencyGraph from './DependencyGraph';
import 'reactflow/dist/style.css';

// Metric Info Definitions
const METRIC_INFO = {
  loc: "Lines of Code: Total number of lines in your codebase (excluding comments and blank lines).",
  files: "Total Files: Number of source code files analyzed.",
  avg_complexity: "Average Cyclomatic Complexity: Measures code complexity based on decision points. Lower is better.",
  max_complexity: "Maximum Cyclomatic Complexity: Highest complexity found in any single function.",
  tech_debt_score: "Technical Debt Score: Estimated effort (in minutes) to address code quality issues.",
  dependencies: "Total Dependencies: Number of unique imports/dependencies in your codebase.",
  duplicate_groups: "Duplicate Code Groups: Number of similar code blocks detected."
};

const GRAPH_INFO = {
  title: "Dependency Graph Visualization",
  description: "Interactive visualization of file dependencies. Nodes represent files, edges show imports."
};

const DEPENDENCY_LIST_INFO = {
  title: "Dependency Analysis",
  description: "Detailed list of all file dependencies and their import relationships."
};

function Tooltip({ info, children, position = 'right' }) {
  const [show, setShow] = useState(false);
  
  return (
    <div className="relative inline-block">
      <div
        onMouseEnter={() => setShow(true)}
        onMouseLeave={() => setShow(false)}
      >
        {children}
      </div>
      {show && (
        <div className={`absolute z-50 w-64 p-3 bg-slate-800 text-white text-xs rounded-lg shadow-xl ${
          position === 'right' ? 'left-full ml-2 top-0' : 'right-full mr-2 top-0'
        }`}>
          {info}
        </div>
      )}
    </div>
  );
}

// Helper Components
function MetricCard({ icon, label, value, color, badge, info, tooltipPosition = 'right' }) {
  const colorClasses = {
    blue: 'bg-blue-100 text-blue-600',
    yellow: 'bg-yellow-100 text-yellow-600',
    purple: 'bg-purple-100 text-purple-600',
    red: 'bg-red-100 text-red-600',
    green: 'bg-green-100 text-green-600',
  };
  const bgColor = colorClasses[color] || 'bg-slate-100 text-slate-600';

  return (
    <div className="bg-slate-50 rounded-lg p-5 border border-slate-200 h-full flex flex-col">
      <div className={`inline-flex p-2 rounded-lg ${bgColor} mb-3 self-start`}>
        {icon}
      </div>
      <div className="flex items-center gap-2 text-sm text-slate-600 mb-1">
        <span>{label}</span>
        {info && (
          <Tooltip info={info} position={tooltipPosition}>
            <Info className="w-4 h-4 text-slate-400 hover:text-slate-600 transition-colors" />
          </Tooltip>
        )}
      </div>
      <div className={`text-2xl font-bold text-slate-800 mt-auto ${badge ? '' : 'pt-2'}`}>
        <span className={badge ? `inline-block px-3 py-1 rounded-lg ${badge}` : ''}>
           {value}
        </span>
      </div>
    </div>
  );
}

function InfoRow({ label, value, valueClass = 'text-slate-800', info }) {
  return (
    <div className="flex justify-between items-center py-1">
      <div className="flex items-center gap-2">
        <span className="text-sm text-slate-600">{label}</span>
        {info && (
          <Tooltip info={info}>
            <Info className="w-3.5 h-3.5 text-slate-400 hover:text-slate-600 transition-colors" />
          </Tooltip>
        )}
      </div>
      <span className={`text-sm font-semibold ${valueClass}`}>{value}</span>
    </div>
  );
}

function ComplexityBar({ label, value, total, color }) {
  const numericValue = typeof value === 'number' ? value : 0;
  const numericTotal = typeof total === 'number' && total > 0 ? total : 0;
  const percentage = numericTotal > 0 ? (numericValue / numericTotal) * 100 : 0;
  const displayValue = numericTotal > 0 ? numericValue.toLocaleString() : 'N/A';

  return (
    <div>
      <div className="flex justify-between items-center mb-1">
        <span className="text-sm text-slate-600">{label}</span>
        <span className="text-sm font-semibold text-slate-800">{displayValue}</span>
      </div>
      <div className="w-full bg-slate-200 rounded-full h-2 overflow-hidden">
        <div
          className={`${color} h-2 rounded-full transition-all duration-300 ease-out`}
          style={{ width: `${percentage}%` }}
          role="progressbar"
          aria-valuenow={percentage}
          aria-valuemin="0"
          aria-valuemax="100"
          aria-label={`${label} complexity percentage`}
        />
      </div>
    </div>
  );
}

function DuplicatePairRow({ item }) {
  const similarityValue = item?.similarity ?? 0;
  const similarityPercentage = (similarityValue * 100).toFixed(1);
  let colorClass = 'bg-yellow-100 text-yellow-800';
  let borderColor = 'border-yellow-200';
  if (similarityValue >= 0.95) {
    colorClass = 'bg-red-100 text-red-800';
    borderColor = 'border-red-200';
  } else if (similarityValue >= 0.90) {
     colorClass = 'bg-orange-100 text-orange-800';
     borderColor = 'border-orange-200';
  }

  return (
    <div className={`p-3 bg-white rounded border ${borderColor}`}>
      <div className="flex justify-between items-center mb-1">
        <span className="text-xs text-slate-700 font-mono truncate flex-1" title={item?.file_a ?? ''}>
            {item?.file_a ?? 'N/A'}
        </span>
        <span className={`ml-3 px-2 py-0.5 ${colorClass} rounded-full text-xs font-medium whitespace-nowrap`}>
          {similarityPercentage}%
        </span>
      </div>
      <div className="flex justify-between items-center">
        <span className="text-xs text-slate-700 font-mono truncate flex-1" title={item?.file_b ?? ''}>
            {item?.file_b ?? 'N/A'}
        </span>
      </div>
    </div>
  );
}

// Main Component
export default function RefractorIQDashboard() {
  const [repoUrl, setRepoUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const [analysisData, setAnalysisData] = useState(null);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState('metrics');
  const [excludeThirdParty, setExcludeThirdParty] = useState(true);
  const [excludeTests, setExcludeTests] = useState(true);
  const [jobId, setJobId] = useState(null);
  const [jobStatus, setJobStatus] = useState(null);
  const [isPolling, setIsPolling] = useState(false);
  const pollIntervalRef = useRef(null);
  const BACKEND_URL = 'https://fluffy-fortnight-pjr95546qg936qrg-8000.app.github.dev';
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [isSearching, setIsSearching] = useState(false);
  const [searchError, setSearchError] = useState(null);
  const currentSearchJobId = useRef(null);

  const pollJobStatus = async (currentJobId) => {
    try {
      const statusUrl = `/analyze/status/${currentJobId}`;
      const response = await fetch(`${BACKEND_URL}${statusUrl}`);
      if (!response.ok) {
          console.error("Status check failed with:", response.status, await response.text());
          throw new Error(`Failed to get job status (${response.status})`);
      }
      const data = await response.json();
      setJobStatus(data.status);

      if (data.status === "COMPLETED") {
        setIsPolling(false);
        setJobId(null);
        setJobStatus(null);
        clearInterval(pollIntervalRef.current);
        const resultsUrl = data.results_url;
        const resultsResponse = await fetch(`${BACKEND_URL}${resultsUrl}`);
        if (!resultsResponse.ok) {
            console.error("Results fetch failed with:", resultsResponse.status, await resultsResponse.text());
            throw new Error(`Failed to fetch final results (${resultsResponse.status})`);
        }
        const resultsData = await resultsResponse.json();
        setAnalysisData(resultsData);
        setLoading(false);
      } else if (data.status === "FAILED") {
        setIsPolling(false);
        setJobId(null);
        setJobStatus(null);
        clearInterval(pollIntervalRef.current);
        setError(data.error || "Analysis job failed");
        setLoading(false);
      }
    } catch (err) {
      console.error("Polling error:", err);
      setIsPolling(false);
      if (pollIntervalRef.current) {
         clearInterval(pollIntervalRef.current);
      }
      setError(err.message || "Polling error occurred.");
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isPolling && jobId) {
      pollJobStatus(jobId);
      pollIntervalRef.current = setInterval(() => {
        if (isPolling && jobId) {
             pollJobStatus(jobId);
        } else if (pollIntervalRef.current) {
             clearInterval(pollIntervalRef.current);
        }
      }, 5000);
    } else if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
    }
    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }
    };
  }, [isPolling, jobId]);

  const analyzeRepo = async () => {
    if (!repoUrl.trim()) {
      setError('Please enter a repository URL');
      return;
    }
    setLoading(true);
    setError(null);
    setAnalysisData(null);
    setJobId(null);
    setJobStatus(null);
    setIsPolling(false);
    setActiveTab('metrics');
    setSearchQuery('');
    setSearchResults([]);
    setSearchError(null);
    currentSearchJobId.current = null;

    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
    }

    try {
      const response = await fetch(`${BACKEND_URL}/analyze/full?repo_url=${encodeURIComponent(repoUrl)}&exclude_third_party=${excludeThirdParty}&exclude_tests=${excludeTests}`);
      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.error || `Failed to start analysis (${response.status})`);
      }
      const data = await response.json();
      setJobId(data.job_id);
      setJobStatus("PENDING");
      setIsPolling(true);
      currentSearchJobId.current = data.job_id;
    } catch (err) {
      console.error("Error starting analysis:", err);
      setError(err.message || 'Failed to start analysis');
      setLoading(false);
      setIsPolling(false);
    }
  };

  const handleSearch = async (e) => {
    e.preventDefault();
    if (!searchQuery.trim() || !analysisData || !currentSearchJobId.current || loading || isSearching) {
      setSearchResults([]);
      setSearchError(null);
      return;
    }
    setIsSearching(true);
    setSearchError(null);
    setSearchResults([]);

    try {
      const searchUrl = `${BACKEND_URL}/analyze/results/${currentSearchJobId.current}/search?q=${encodeURIComponent(searchQuery)}&k=10`;
      const response = await fetch(searchUrl);
      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.detail || `Search request failed (${response.status})`);
      }
      const data = await response.json();
      setSearchResults(data.results || []);
      if (!data.results || data.results.length === 0) {
          setSearchError(`No relevant results found for "${searchQuery}". Try different keywords.`);
      }
    } catch (err) {
      console.error("Search error:", err);
      setSearchError(err.message || 'Failed to fetch search results.');
    } finally {
      setIsSearching(false);
    }
  };

  const getComplexityColor = (complexity) => {
    if (complexity === undefined || complexity === null) return 'text-slate-800';
    if (complexity <= 5) return 'text-green-600';
    if (complexity <= 10) return 'text-yellow-600';
    if (complexity <= 20) return 'text-orange-600';
    return 'text-red-600';
  };

  const getDebtScoreColor = (score) => {
    if (score === undefined || score === null || score < 50) return 'bg-green-100 text-green-800';
    if (score < 100) return 'bg-yellow-100 text-yellow-800';
    if (score < 200) return 'bg-orange-100 text-orange-800';
    return 'bg-red-100 text-red-800';
  };

  const normalizeValue = (value, metricKey) => {
    if (value === undefined || value === null) return 'N/A';
    if (metricKey === 'loc' && typeof value === 'number' && value > 1000) {
      return `${(value / 1000).toFixed(1)}K`;
    }
    if (typeof value === 'number') {
       return value.toLocaleString();
    }
    return String(value);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100">
      {/* Header */}
      <div className="bg-white border-b border-slate-200 shadow-sm">
        <div className="max-w-7xl mx-auto px-6 py-6">
          <div className="flex items-center gap-3 mb-4">
            <BrainCircuit className="w-8 h-8 text-blue-600" />
            <h1 className="text-3xl font-bold text-slate-800">RefractorIQ</h1>
          </div>
          <p className="text-slate-600">AI-powered code analysis and technical debt detection</p>
        </div>
      </div>

      {/* Search Section */}
      <div className="max-w-7xl mx-auto px-6 py-8">
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
          <div className="flex gap-4 mb-4">
            <div className="flex-1">
              <input
                type="text"
                placeholder="Enter GitHub repository URL..."
                value={repoUrl}
                onChange={(e) => setRepoUrl(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && analyzeRepo()}
                className="w-full px-4 py-3 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none"
                disabled={loading}
              />
            </div>
            <button
              onClick={analyzeRepo}
              disabled={loading}
              className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-slate-300 disabled:cursor-not-allowed flex items-center gap-2 font-medium transition-colors"
            >
              {loading ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" />
                  Analyzing...
                </>
              ) : (
                <>
                  <Github className="w-5 h-5" />
                  Analyze
                </>
              )}
            </button>
          </div>
          
          <div className="flex gap-4 text-sm">
            <label className="flex items-center gap-2 text-slate-600">
              <input
                type="checkbox"
                checked={excludeThirdParty}
                onChange={(e) => setExcludeThirdParty(e.target.checked)}
                disabled={loading}
                className="rounded"
              />
              Exclude third-party code
            </label>
            <label className="flex items-center gap-2 text-slate-600">
              <input
                type="checkbox"
                checked={excludeTests}
                onChange={(e) => setExcludeTests(e.target.checked)}
                disabled={loading}
                className="rounded"
              />
              Exclude test files
            </label>
          </div>
        </div>

        {/* Loading Indicator */}
        {loading && (
          <div className="mt-6 bg-white rounded-xl shadow-sm border border-slate-200 p-8">
            <div className="flex flex-col items-center justify-center">
              <Loader2 className="w-12 h-12 text-blue-600 animate-spin mb-4" />
              <p className="text-lg font-medium text-slate-800 mb-2">
                {jobStatus === 'PENDING' && 'Queueing analysis...'}
                {jobStatus === 'RUNNING' && 'Analyzing repository...'}
                {!jobStatus && 'Starting analysis...'}
              </p>
              <p className="text-sm text-slate-600">This may take a minute</p>
            </div>
          </div>
        )}

        {/* Error Display */}
        {error && (
          <div className="mt-6 bg-red-50 border border-red-200 rounded-xl p-4 flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-red-800 font-medium">Analysis Failed</p>
              <p className="text-red-700 text-sm mt-1">{error}</p>
            </div>
          </div>
        )}

        {/* Results Display */}
        {analysisData && !loading && (
          <div className="mt-6 space-y-6">
            {/* Success Header */}
            <div className="bg-green-50 border border-green-200 rounded-xl p-4 flex items-center gap-3">
              <CheckCircle className="w-5 h-5 text-green-600" />
              <p className="text-green-800 font-medium">Analysis complete!</p>
            </div>

            {/* Search Bar */}
            <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
              <div className="flex gap-4">
                <div className="flex-1">
                  <input
                    type="text"
                    placeholder="Search codebase... (e.g., 'authentication logic', 'database queries')"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    onKeyPress={(e) => e.key === 'Enter' && handleSearch(e)}
                    className="w-full px-4 py-3 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none"
                    disabled={isSearching}
                  />
                </div>
                <button
                  onClick={handleSearch}
                  disabled={isSearching || !searchQuery.trim()}
                  className="px-6 py-3 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:bg-slate-300 disabled:cursor-not-allowed flex items-center gap-2 font-medium transition-colors"
                >
                  {isSearching ? (
                    <>
                      <Loader2 className="w-5 h-5 animate-spin" />
                      Searching...
                    </>
                  ) : (
                    <>
                      <Search className="w-5 h-5" />
                      Search
                    </>
                  )}
                </button>
              </div>

              {/* Search Results */}
              {searchResults.length > 0 && (
                <div className="mt-6 space-y-3">
                  <h3 className="text-lg font-semibold text-slate-800 flex items-center gap-2">
                    <FileText className="w-5 h-5" />
                    Search Results ({searchResults.length})
                  </h3>
                  {searchResults.map((result, idx) => (
                    <div key={idx} className="border border-slate-200 rounded-lg p-4 bg-slate-50">
                      <div className="flex items-start justify-between mb-2">
                        <span className="font-mono text-sm text-blue-600 font-medium">{result.file_path}</span>
                        <span className="text-xs text-slate-500">Score: {result.score?.toFixed(3)}</span>
                      </div>
                      <p className="text-sm text-slate-700">{result.content}</p>
                    </div>
                  ))}
                </div>
              )}

              {searchError && (
                <div className="mt-4 text-sm text-slate-600 flex items-center gap-2">
                  <AlertCircle className="w-4 h-4" />
                  {searchError}
                </div>
              )}
            </div>

            {/* Tabs */}
            <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
              <div className="border-b border-slate-200">
                <div className="flex">
                  {['metrics', 'dependencies', 'graph', 'duplication'].map((tab) => (
                    <button
                      key={tab}
                      onClick={() => setActiveTab(tab)}
                      className={`px-6 py-4 font-medium transition-colors ${
                        activeTab === tab
                          ? 'text-blue-600 border-b-2 border-blue-600 bg-blue-50'
                          : 'text-slate-600 hover:text-slate-800 hover:bg-slate-50'
                      }`}
                    >
                      {tab.charAt(0).toUpperCase() + tab.slice(1)}
                    </button>
                  ))}
                </div>
              </div>

              <div className="p-6">
                {/* Metrics Tab */}
                {activeTab === 'metrics' && (
                  <div className="space-y-6">
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                      <MetricCard
                        icon={<FileCode className="w-5 h-5" />}
                        label="Lines of Code"
                        value={normalizeValue(analysisData.metrics?.loc, 'loc')}
                        color="blue"
                        info={METRIC_INFO.loc}
                      />
                      <MetricCard
                        icon={<Package className="w-5 h-5" />}
                        label="Total Files"
                        value={normalizeValue(analysisData.metrics?.files)}
                        color="purple"
                        info={METRIC_INFO.files}
                      />
                      <MetricCard
                        icon={<TrendingUp className="w-5 h-5" />}
                        label="Avg Complexity"
                        value={analysisData.metrics?.avg_complexity?.toFixed(1) || 'N/A'}
                        color="yellow"
                        info={METRIC_INFO.avg_complexity}
                      />
                      <MetricCard
                        icon={<Zap className="w-5 h-5" />}
                        label="Tech Debt Score"
                        value={normalizeValue(analysisData.metrics?.tech_debt_score)}
                        color="red"
                        badge={getDebtScoreColor(analysisData.metrics?.tech_debt_score)}
                        info={METRIC_INFO.tech_debt_score}
                      />
                    </div>

                    {analysisData.complexity_distribution && (
                      <div className="bg-slate-50 rounded-lg p-5 border border-slate-200">
                        <h3 className="text-lg font-semibold text-slate-800 mb-4">Complexity Distribution</h3>
                        <div className="space-y-3">
                          <ComplexityBar
                            label="Low (1-5)"
                            value={analysisData.complexity_distribution.low}
                            total={analysisData.complexity_distribution.total}
                            color="bg-green-500"
                          />
                          <ComplexityBar
                            label="Medium (6-10)"
                            value={analysisData.complexity_distribution.medium}
                            total={analysisData.complexity_distribution.total}
                            color="bg-yellow-500"
                          />
                          <ComplexityBar
                            label="High (11-20)"
                            value={analysisData.complexity_distribution.high}
                            total={analysisData.complexity_distribution.total}
                            color="bg-orange-500"
                          />
                          <ComplexityBar
                            label="Very High (20+)"
                            value={analysisData.complexity_distribution.very_high}
                            total={analysisData.complexity_distribution.total}
                            color="bg-red-500"
                          />
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {/* Dependencies Tab */}
                {activeTab === 'dependencies' && (
                  <div className="space-y-4">
                    <div className="flex items-center gap-2 mb-4">
                      <h3 className="text-lg font-semibold text-slate-800">Dependencies</h3>
                      <Tooltip info={DEPENDENCY_LIST_INFO.description}>
                        <Info className="w-4 h-4 text-slate-400 hover:text-slate-600 transition-colors" />
                      </Tooltip>
                    </div>
                    {analysisData.dependencies && analysisData.dependencies.length > 0 ? (
                      <div className="space-y-2">
                        {analysisData.dependencies.map((dep, idx) => (
                          <div key={idx} className="bg-slate-50 rounded-lg p-4 border border-slate-200">
                            <div className="font-mono text-sm text-blue-600 font-medium mb-2">{dep.file}</div>
                            {dep.imports && dep.imports.length > 0 && (
                              <div className="text-xs text-slate-600">
                                Imports: {dep.imports.join(', ')}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="text-slate-600">No dependencies found</p>
                    )}
                  </div>
                )}

                {/* Graph Tab */}
                {activeTab === 'graph' && (
                  <div>
                    <div className="flex items-center gap-2 mb-4">
                      <h3 className="text-lg font-semibold text-slate-800">Dependency Graph</h3>
                      <Tooltip info={GRAPH_INFO.description}>
                        <Info className="w-4 h-4 text-slate-400 hover:text-slate-600 transition-colors" />
                      </Tooltip>
                    </div>
                    <div className="bg-slate-50 rounded-lg border border-slate-200" style={{ height: '600px' }}>
                      <ReactFlowProvider>
                        <DependencyGraph dependencies={analysisData.dependencies || []} />
                      </ReactFlowProvider>
                    </div>
                  </div>
                )}

                {/* Duplication Tab */}
                {activeTab === 'duplication' && (
                  <div className="space-y-4">
                    <h3 className="text-lg font-semibold text-slate-800 flex items-center gap-2">
                      <CopyCheck className="w-5 h-5" />
                      Code Duplication
                    </h3>
                    {analysisData.duplicate_code && analysisData.duplicate_code.length > 0 ? (
                      <div className="space-y-3">
                        {analysisData.duplicate_code.map((item, idx) => (
                          <DuplicatePairRow key={idx} item={item} />
                        ))}
                      </div>
                    ) : (
                      <p className="text-slate-600">No duplicate code detected</p>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
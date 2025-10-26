// RefractorIQ/frontend/src/App.jsx

import React, { useState, useEffect, useRef } from 'react';
// --- Info icon imported ---
import { Search, Github, AlertCircle, CheckCircle, TrendingUp, GitBranch, FileCode, Zap, Info, Package, TestTube, CopyCheck, Loader2, Share2 } from 'lucide-react';

// --- React Flow Imports ---
import { ReactFlowProvider } from 'reactflow';
import DependencyGraph from './DependencyGraph';
import 'reactflow/dist/style.css';


// --- METRIC_INFO unchanged ---
const METRIC_INFO = {
  loc: { title: "Lines of Code", description: "Total number of code lines excluding comments and blank lines. Measured using AST parsing.", interpretation: "Lower is often better for maintainability. Industry average: 10,000-50,000 LOC per project." },
  todos: { title: "TODOs/FIXMEs/HACKs", description: "Count of TODO, FIXME, and HACK comments in the codebase indicating pending work or technical shortcuts.", interpretation: "Lower is better. High counts may indicate incomplete features or deferred refactoring." },
  avgComplexity: { title: "Average Cyclomatic Complexity", description: "Average complexity across all functions. Measures the number of independent paths through code.", interpretation: "1-5: Simple, 6-10: Moderate, 11-20: Complex, 21+: Very Complex. Lower is better for maintainability." },
  debtScore: { title: "Technical Debt Score", description: "Composite score calculated from TODOs (×5), complexity (×2), and LOC (÷1000). Higher scores indicate more technical debt.", interpretation: "<50: Low debt, 50-100: Moderate, 100-200: High, 200+: Critical. Lower is better." },
  totalFunctions: { title: "Total Functions", description: "Total count of all functions and methods across the codebase including Python functions, JS/TS functions, arrow functions, and class methods.", interpretation: "Indicates codebase size and modularity. No strict good/bad threshold." },
  filesAnalyzed: { title: "Files Analyzed", description: "Number of source code files successfully parsed and analyzed (.py, .js, .ts, .java).", interpretation: "Should match expected file count. Lower than expected may indicate parsing issues." },
  maxComplexity: { title: "Maximum Complexity", description: "Highest cyclomatic complexity value found in any single function.", interpretation: "Values >20 indicate functions that should be refactored. Ideal: <10" },
  minComplexity: { title: "Minimum Complexity", description: "Lowest cyclomatic complexity value found in any single function.", interpretation: "Usually 1 for simple functions. Indicates simplest code unit." },
  totalFiles: { title: "Total Files", description: "Total number of source code files included in dependency analysis.", interpretation: "Indicates project size. More files require better organization." },
  depFunctions: { title: "External Dependencies", description: "Count of third-party libraries and external modules imported by the codebase from npm, PyPI, Maven, etc.", interpretation: "Monitor for security and maintenance. Each dependency is a potential risk vector. Fewer dependencies = less complexity." },
  classes: { title: "Total Classes", description: "Number of class definitions found across the codebase.", interpretation: "Indicates OOP usage. Higher doesn't mean better - depends on design approach." },
  circularDeps: { title: "Circular Dependencies", description: "Number of circular dependency chains detected where files depend on each other in a cycle.", interpretation: "0 is ideal. Any circular dependencies should be refactored to prevent maintenance issues." },
  excludeThirdParty: { title: "Exclude Third-Party Libraries", description: "When enabled, excludes common third-party library directories (node_modules, venv, site-packages, vendor, etc.) from analysis. On the 'Dependencies' tab, this also hides externally imported libraries.", interpretation: "Enable to focus on your code. Note: Most repos .gitignore these folders, so 'Code Metrics' (like LOC) may not change. The 'Dependencies' tab will still update to hide/show external imports." },
  excludeTests: { title: "Exclude Test Files", description: "When enabled, excludes files matching common test patterns (e.g., _test.py, .spec.js, test_*, tests/) from all analysis.", interpretation: "Enable this to focus on your application's production code and get a cleaner dependency graph. Disable to include tests in the metrics." },
  duplicatePairs: { title: "Duplicate Pairs Found", description: "Number of pairs of files found that are considered duplicates based on content similarity (default threshold: 85%).", interpretation: "Uses MinHash (datasketch) to find Jaccard similarity. High numbers of duplicates can indicate copy-paste code and poor abstraction." },
  duplicationFilesAnalyzed: { title: "Files Analyzed for Duplication", description: "Number of files processed by the duplication engine.", interpretation: "This number may match 'Files Analyzed' in Code Metrics, depending on exclusions." }
};

// --- Tooltip Component ---
function Tooltip({ info, children, position = 'right' }) {
  const [show, setShow] = useState(false);
  const getPositionClasses = () => { /* ... */ if (position === 'left') return 'right-full mr-3 top-1/2 -translate-y-1/2'; return 'left-full ml-3 top-1/2 -translate-y-1/2'; };
  const getArrowClasses = () => { /* ... */ if (position === 'left') return '-right-1.5 top-1/2 -translate-y-1/2'; return '-left-1.5 top-1/2 -translate-y-1/2'; };
  return (
    <div className="relative inline-block">
      <div onMouseEnter={() => setShow(true)} onMouseLeave={() => setShow(false)} className="cursor-help"> {children} </div>
      {show && (
        <div className={`absolute z-50 w-80 p-4 bg-slate-900 text-white rounded-lg shadow-xl pointer-events-none ${getPositionClasses()}`}>
          <div className={`absolute w-3 h-3 bg-slate-900 transform rotate-45 ${getArrowClasses()}`}></div>
          <h4 className="font-semibold text-sm mb-2 text-blue-300">{info.title}</h4>
          <p className="text-xs text-slate-300 mb-2">{info.description}</p>
          {info.interpretation && <p className="text-xs text-slate-400 italic">{info.interpretation}</p>}
        </div>
      )}
    </div>
  );
}

// --- Graph Info ---
const GRAPH_INFO = {
    title: "Dependency Graph Guide",
    description: "Visualizes file relationships. Nodes are colored by parent folder. Blue nodes = files, Green = external libraries, Orange = functions/classes. Solid blue lines = 'imports' relationship. Dashed orange lines = 'defines' relationship (function/class defined in file).",
    interpretation: "Look for clusters of related files (modularity) and circular dependencies. High connectivity might indicate tight coupling."
};

// --- NEW: Dependency List Info ---
const DEPENDENCY_LIST_INFO = {
    title: "Understanding Dependency Counts",
    description: "'Most Dependent Files' lists files that import *many* others (high out-degree). 'Most Depended On Files' lists files imported *by many* others (high in-degree).",
    interpretation: "A file can have dependencies (out-degree > 0) but 0 dependents (in-degree = 0) if it's an entry point (like a main script) or if the files importing it were excluded (e.g., test files when 'Exclude Tests' is on)."
};

// --- MAIN APP COMPONENT ---
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

  // --- Polling and Analyze Functions (unchanged) ---
  const pollJobStatus = async (currentJobId) => { /* ... */
    try {
      const statusUrl = `/analyze/status/${currentJobId}`; const response = await fetch(`${BACKEND_URL}${statusUrl}`);
      if (!response.ok) throw new Error("Failed to get job status"); const data = await response.json();
      setJobStatus(data.status);
      if (data.status === "COMPLETED") {
        setIsPolling(false); setJobId(null); setJobStatus(null); clearInterval(pollIntervalRef.current);
        const resultsUrl = data.results_url; const resultsResponse = await fetch(`${BACKEND_URL}${resultsUrl}`);
        if (!resultsResponse.ok) throw new Error("Failed to fetch final results");
        const resultsData = await resultsResponse.json(); setAnalysisData(resultsData); setLoading(false);
      } else if (data.status === "FAILED") {
        setIsPolling(false); setJobId(null); setJobStatus(null); clearInterval(pollIntervalRef.current);
        setError(data.error || "Analysis job failed"); setLoading(false);
      }
    } catch (err) { console.error("Polling error:", err); setIsPolling(false); clearInterval(pollIntervalRef.current); setError(err.message || "Polling error"); setLoading(false); }
  };
  useEffect(() => { /* ... */
    if (isPolling && jobId) { pollJobStatus(jobId); pollIntervalRef.current = setInterval(() => { pollJobStatus(jobId); }, 5000); }
    return () => { if (pollIntervalRef.current) clearInterval(pollIntervalRef.current); };
  }, [isPolling, jobId]);
  const analyzeRepo = async () => { /* ... */
    if (!repoUrl.trim()) { setError('Please enter a repository URL'); return; }
    setLoading(true); setError(null); setAnalysisData(null); setJobId(null); setJobStatus(null);
    setIsPolling(false); setActiveTab('metrics'); if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
    try {
      const response = await fetch(`${BACKEND_URL}/analyze/full?repo_url=${encodeURIComponent(repoUrl)}&exclude_third_party=${excludeThirdParty}&exclude_tests=${excludeTests}`);
      if (!response.ok) { const errData = await response.json(); throw new Error(errData.error || 'Failed to start analysis'); }
      const data = await response.json(); setJobId(data.job_id); setJobStatus("PENDING"); setIsPolling(true);
    } catch (err) { console.error("Error starting analysis:", err); setError(err.message || 'Failed to start analysis'); setLoading(false); }
  };

  // --- Helper Functions (unchanged) ---
  const getComplexityColor = (complexity) => { /* ... */ if (complexity <= 5) return 'text-green-600'; if (complexity <= 10) return 'text-yellow-600'; if (complexity <= 20) return 'text-orange-600'; return 'text-red-600'; };
  const getDebtScoreColor = (score) => { /* ... */ if (!score || score < 50) return 'bg-green-100 text-green-800'; if (score < 100) return 'bg-yellow-100 text-yellow-800'; if (score < 200) return 'bg-orange-100 text-orange-800'; return 'bg-red-100 text-red-800'; };
  const normalizeValue = (value, metricKey) => { /* ... */ if (value === undefined || value === null) return 'N/A'; if (metricKey === 'loc' && typeof value === 'number' && value > 1000) return `${(value / 1000).toFixed(1)}K`; if (typeof value === 'number') return value.toLocaleString(); return value; };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100">
      {/* Header (unchanged) */}
      <div className="bg-white shadow-sm border-b border-slate-200"> {/* ... */}
        <div className="max-w-7xl mx-auto px-6 py-4"> <div className="flex items-center gap-3"> <div className="bg-gradient-to-br from-blue-500 to-purple-600 p-2 rounded-lg"> <FileCode className="w-6 h-6 text-white" /> </div> <div> <h1 className="text-2xl font-bold text-slate-800">RefractorIQ</h1> <p className="text-sm text-slate-500">Code Quality Analysis Dashboard</p> </div> </div> </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 py-8">
        {/* Search Section (unchanged) */}
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 mb-6"> {/* ... */}
          <div className="flex gap-3 mb-4"> <div className="flex-1 relative"> <Github className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" /> <input type="text" value={repoUrl} onChange={(e) => setRepoUrl(e.target.value)} onKeyPress={(e) => e.key === 'Enter' && analyzeRepo()} placeholder="Enter GitHub repository URL (e.g., https://github.com/user/repo)" className="w-full pl-11 pr-4 py-3 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none disabled:bg-slate-100" disabled={loading} /> </div> <button onClick={analyzeRepo} disabled={loading} className="px-6 py-3 bg-gradient-to-r from-blue-500 to-purple-600 text-white rounded-lg font-medium hover:shadow-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"> {loading ? (<><Loader2 className="w-5 h-5 animate-spin" />{jobStatus ? jobStatus : 'Starting...'}</>) : (<><Search className="w-5 h-5" />Analyze</>)} </button> </div> <div className="space-y-3"> <div className="flex items-center gap-3 p-4 bg-slate-50 rounded-lg border border-slate-200"> <label className={`flex items-center gap-3 flex-1 ${loading ? 'cursor-not-allowed opacity-50' : 'cursor-pointer'}`}> <div className="relative"> <input type="checkbox" checked={excludeThirdParty} onChange={(e) => setExcludeThirdParty(e.target.checked)} className="sr-only peer" disabled={loading} /> <div className="w-11 h-6 bg-slate-300 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div> </div> <div className="flex items-center gap-2"> <Package className="w-5 h-5 text-slate-600" /> <span className="text-sm font-medium text-slate-700">Exclude Third-Party Libraries</span> </div> </label> <Tooltip info={METRIC_INFO.excludeThirdParty} position="left"> <Info className="w-5 h-5 text-slate-400 hover:text-slate-600 transition-colors cursor-help" /> </Tooltip> </div> <div className="flex items-center gap-3 p-4 bg-slate-50 rounded-lg border border-slate-200"> <label className={`flex items-center gap-3 flex-1 ${loading ? 'cursor-not-allowed opacity-50' : 'cursor-pointer'}`}> <div className="relative"> <input type="checkbox" checked={excludeTests} onChange={(e) => setExcludeTests(e.target.checked)} className="sr-only peer" disabled={loading} /> <div className="w-11 h-6 bg-slate-300 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div> </div> <div className="flex items-center gap-2"> <TestTube className="w-5 h-5 text-slate-600" /> <span className="text-sm font-medium text-slate-700">Exclude Test Files</span> </div> </label> <Tooltip info={METRIC_INFO.excludeTests} position="left"> <Info className="w-5 h-5 text-slate-400 hover:text-slate-600 transition-colors cursor-help" /> </Tooltip> </div> </div> {error && !loading && ( <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-lg flex items-center gap-3"> <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0" /> <p className="text-red-800">{error}</p> </div> )}
        </div>

        {/* Loading Indicator (unchanged) */}
        {loading && jobId && ( /* ... */
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 text-center"> <Loader2 className="w-12 h-12 text-blue-500 mx-auto mb-4 animate-spin" /> <h3 className="text-lg font-semibold text-slate-800">Analysis in Progress</h3> <p className="text-sm text-slate-600 mb-2">Status: <span className="font-medium text-blue-600">{jobStatus || 'Initializing...'}</span></p> <p className="text-xs text-slate-500 font-mono">Job ID: {jobId}</p> <p className="text-sm text-slate-600 mt-4">This may take several minutes. Please wait...</p> </div>
        )}

        {/* --- Results Display --- */}
        {analysisData && !loading && (
          <div className="space-y-6">
            <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6"> {/* ... Analysis Complete header ... */}
              <div className="flex items-center justify-between"> <div className="flex items-center gap-3"> <CheckCircle className="w-6 h-6 text-green-600" /> <div> <h2 className="text-xl font-bold text-slate-800">Analysis Complete</h2> <p className="text-slate-600 break-all">{analysisData?.repository ?? 'N/A'}</p> </div> </div> <div className="flex flex-col items-end gap-1"> {analysisData?.excluded_third_party && ( <div className="flex items-center gap-2 px-3 py-1.5 bg-blue-50 border border-blue-200 rounded-lg"> <Package className="w-4 h-4 text-blue-600" /> <span className="text-xs font-medium text-blue-700">Third-party excluded</span> </div> )} {analysisData?.excluded_tests && ( <div className="flex items-center gap-2 px-3 py-1.5 bg-green-50 border border-green-200 rounded-lg"> <TestTube className="w-4 h-4 text-green-600" /> <span className="text-xs font-medium text-green-700">Tests excluded</span> </div> )} </div> </div>
            </div>

            {/* --- TABS Container --- */}
            <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
              {/* Tab Buttons (unchanged) */}
              <div className="flex border-b border-slate-200"> {/* ... */}
                 <button onClick={() => setActiveTab('metrics')} className={`flex-1 px-6 py-4 font-medium transition-colors ${activeTab === 'metrics' ? 'bg-blue-50 text-blue-600 border-b-2 border-blue-600' : 'text-slate-600 hover:bg-slate-50'}`}>Code Metrics</button>
                 <button onClick={() => setActiveTab('dependencies')} className={`flex-1 px-6 py-4 font-medium transition-colors ${activeTab === 'dependencies' ? 'bg-blue-50 text-blue-600 border-b-2 border-blue-600' : 'text-slate-600 hover:bg-slate-50'}`}>Dependencies</button>
                 <button onClick={() => setActiveTab('graph')} className={`flex items-center justify-center gap-2 flex-1 px-6 py-4 font-medium transition-colors ${activeTab === 'graph' ? 'bg-blue-50 text-blue-600 border-b-2 border-blue-600' : 'text-slate-600 hover:bg-slate-50'}`}><Share2 className="w-4 h-4" />Dependency Graph</button>
                 <button onClick={() => setActiveTab('duplication')} className={`flex-1 px-6 py-4 font-medium transition-colors ${activeTab === 'duplication' ? 'bg-blue-50 text-blue-600 border-b-2 border-blue-600' : 'text-slate-600 hover:bg-slate-50'}`}>Duplication</button>
              </div>

              {/* Tab Panels */}
              <div className="p-6">
                {/* Metrics Tab (unchanged) */}
                {activeTab === 'metrics' && ( /* ... */
                  <div className="space-y-6"> <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4"> <MetricCard icon={<FileCode className="w-5 h-5" />} label="Lines of Code" value={normalizeValue(analysisData?.code_metrics?.LOC, 'loc')} color="blue" info={METRIC_INFO.loc} /> <MetricCard icon={<AlertCircle className="w-5 h-5" />} label="TODOs/FIXMEs" value={normalizeValue(analysisData?.code_metrics?.TODOs_FIXME_HACK)} color="yellow" info={METRIC_INFO.todos} /> <MetricCard icon={<TrendingUp className="w-5 h-5" />} label="Avg Complexity" value={normalizeValue(analysisData?.code_metrics?.AvgCyclomaticComplexity)} color="purple" info={METRIC_INFO.avgComplexity} /> <MetricCard icon={<Zap className="w-5 h-5" />} label="Debt Score" value={normalizeValue(analysisData?.code_metrics?.DebtScore)} color="red" badge={getDebtScoreColor(analysisData?.code_metrics?.DebtScore)} info={METRIC_INFO.debtScore} tooltipPosition="left" /> </div> <div className="grid grid-cols-1 md:grid-cols-2 gap-6"> <div className="bg-slate-50 rounded-lg p-5 border border-slate-200"> <h3 className="font-semibold text-slate-800 mb-4">Function Analysis</h3> <div className="space-y-3"> <InfoRow label="Total Functions" value={normalizeValue(analysisData?.code_metrics?.TotalFunctions)} info={METRIC_INFO.totalFunctions} /> <InfoRow label="Files Analyzed" value={normalizeValue(analysisData?.code_metrics?.FilesAnalyzed)} info={METRIC_INFO.filesAnalyzed} /> <InfoRow label="Max Complexity" value={normalizeValue(analysisData?.code_metrics?.MaxComplexity)} valueClass={getComplexityColor(analysisData?.code_metrics?.MaxComplexity)} info={METRIC_INFO.maxComplexity} /> <InfoRow label="Min Complexity" value={normalizeValue(analysisData?.code_metrics?.MinComplexity)} valueClass={getComplexityColor(analysisData?.code_metrics?.MinComplexity)} info={METRIC_INFO.minComplexity} /> </div> </div> <div className="bg-slate-50 rounded-lg p-5 border border-slate-200"> <h3 className="font-semibold text-slate-800 mb-4">Complexity Distribution</h3> <div className="space-y-3"> <ComplexityBar label="Low (1-5)" value={analysisData?.code_metrics?.ComplexityDistribution?.low ?? 0} total={analysisData?.code_metrics?.TotalFunctions ?? 0} color="bg-green-500" /> <ComplexityBar label="Medium (6-10)" value={analysisData?.code_metrics?.ComplexityDistribution?.medium ?? 0} total={analysisData?.code_metrics?.TotalFunctions ?? 0} color="bg-yellow-500" /> <ComplexityBar label="High (11-20)" value={analysisData?.code_metrics?.ComplexityDistribution?.high ?? 0} total={analysisData?.code_metrics?.TotalFunctions ?? 0} color="bg-orange-500" /> <ComplexityBar label="Very High (21+)" value={analysisData?.code_metrics?.ComplexityDistribution?.very_high ?? 0} total={analysisData?.code_metrics?.TotalFunctions ?? 0} color="bg-red-500" /> </div> </div> </div> </div>
                )}

                {/* --- DEPENDENCIES TAB (MODIFIED) --- */}
                {activeTab === 'dependencies' && (
                  <div className="space-y-6">
                    {/* Metric Cards (unchanged) */}
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4"> {/* ... */}
                      <MetricCard icon={<FileCode className="w-5 h-5" />} label="Total Files" value={normalizeValue(analysisData?.dependency_metrics?.total_files)} color="blue" info={METRIC_INFO.totalFiles} /> <MetricCard icon={<GitBranch className="w-5 h-5" />} label="External Dependencies" value={normalizeValue(analysisData?.dependency_metrics?.total_external_dependencies)} color="green" info={METRIC_INFO.depFunctions} /> <MetricCard icon={<GitBranch className="w-5 h-5" />} label="Classes" value={normalizeValue(analysisData?.dependency_metrics?.total_classes)} color="purple" info={METRIC_INFO.classes} /> <MetricCard icon={<AlertCircle className="w-5 h-5" />} label="Circular Dependencies" value={normalizeValue(analysisData?.dependency_metrics?.circular_dependencies)} color="red" info={METRIC_INFO.circularDeps} tooltipPosition="left" />
                    </div>

                    {/* Most Dependent Files (unchanged) */}
                    {(analysisData?.dependency_metrics?.most_dependent_files?.length ?? 0) > 0 && ( /* ... */
                      <div className="bg-slate-50 rounded-lg p-5 border border-slate-200"> <h3 className="font-semibold text-slate-800 mb-4">Most Dependent Files</h3> <div className="space-y-2 max-h-96 overflow-y-auto"> {analysisData.dependency_metrics.most_dependent_files.map((item, idx) => ( <div key={idx} className="flex justify-between items-center p-3 bg-white rounded border border-slate-200"> <span className="text-sm text-slate-700 font-mono truncate flex-1" title={item.file}>{item.file}</span> <span className="ml-3 px-3 py-1 bg-blue-100 text-blue-800 rounded-full text-sm font-medium whitespace-nowrap">{item.dependencies} deps</span> </div> ))} </div> </div>
                    )}

                    {/* Most Depended On Files (MODIFIED - Added Tooltip) */}
                    {(analysisData?.dependency_metrics?.most_depended_on_files?.length ?? 0) > 0 && (
                       <div className="bg-slate-50 rounded-lg p-5 border border-slate-200">
                        {/* --- ADDED TOOLTIP WRAPPER --- */}
                        <div className="flex items-center gap-2 mb-4">
                            <h3 className="font-semibold text-slate-800">Most Depended On Files</h3>
                            <Tooltip info={DEPENDENCY_LIST_INFO} position="right">
                                <Info className="w-4 h-4 text-slate-400 hover:text-slate-600 transition-colors" />
                            </Tooltip>
                        </div>
                        {/* --- END TOOLTIP WRAPPER --- */}
                        <div className="space-y-2 max-h-96 overflow-y-auto">
                          {analysisData.dependency_metrics.most_depended_on_files.map((item, idx) => (
                            <div key={idx} className="flex justify-between items-center p-3 bg-white rounded border border-slate-200">
                              <span className="text-sm text-slate-700 font-mono truncate flex-1" title={item.file}>{item.file}</span>
                              <span className="ml-3 px-3 py-1 bg-purple-100 text-purple-800 rounded-full text-sm font-medium whitespace-nowrap">
                                {item.dependents} dependents
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
                {/* --- END DEPENDENCIES TAB MODIFICATION --- */}


                {/* Graph Tab (unchanged from previous update) */}
                {activeTab === 'graph' && (
                  <div className="relative w-full h-[600px] bg-slate-50 rounded-lg border border-slate-200">
                     <div className="absolute top-3 right-3 z-10">
                        <Tooltip info={GRAPH_INFO} position="left">
                            <button className="p-2 bg-white/80 backdrop-blur-sm rounded-full shadow border border-slate-300 hover:bg-slate-100 transition-colors">
                                <Info className="w-5 h-5 text-slate-600" />
                            </button>
                        </Tooltip>
                    </div>
                    <ReactFlowProvider>
                      {analysisData?.dependency_metrics?.graph_json ? (
                        <DependencyGraph graphData={analysisData.dependency_metrics.graph_json} />
                      ) : (
                        <div className="flex items-center justify-center h-full"><p className="text-slate-500">Graph data is not available.</p></div>
                      )}
                    </ReactFlowProvider>
                  </div>
                )}

                {/* Duplication Tab (unchanged) */}
                {activeTab === 'duplication' && ( /* ... */
                   <div className="space-y-6"> <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4"> <MetricCard icon={<CopyCheck className="w-5 h-5" />} label="Duplicate Pairs Found" value={normalizeValue(analysisData?.duplication_metrics?.duplicate_pairs_found)} color="yellow" info={METRIC_INFO.duplicatePairs} /> <MetricCard icon={<FileCode className="w-5 h-5" />} label="Files Analyzed" value={normalizeValue(analysisData?.duplication_metrics?.files_analyzed)} color="blue" info={METRIC_INFO.duplicationFilesAnalyzed} /> </div> {analysisData?.duplication_metrics?.error && ( <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-lg flex items-center gap-3"> <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0" /> <p className="text-red-800">Duplication analysis failed: {analysisData.duplication_metrics.error}</p> </div> )} {(analysisData?.duplication_metrics?.duplicates?.length ?? 0) > 0 && ( <div className="bg-slate-50 rounded-lg p-5 border border-slate-200"> <h3 className="font-semibold text-slate-800 mb-4">Duplicate File Pairs (Threshold: {(analysisData?.duplication_metrics?.similarity_threshold ?? 0) * 100}%)</h3> <div className="space-y-2 max-h-96 overflow-y-auto"> {analysisData.duplication_metrics.duplicates.map((item, idx) => ( <DuplicatePairRow key={idx} item={item} /> ))} </div> </div> )} {(!analysisData?.duplication_metrics || (analysisData?.duplication_metrics?.duplicates?.length ?? 0) === 0) && !analysisData?.duplication_metrics?.error && ( <div className="text-center p-6 bg-slate-50 rounded-lg border border-slate-200"> <CheckCircle className="w-12 h-12 text-green-500 mx-auto mb-3" /> <h4 className="font-semibold text-slate-700">No Duplicates Found</h4> <p className="text-sm text-slate-500">No file pairs met the {(analysisData?.duplication_metrics?.similarity_threshold ?? 0) * 100}% similarity threshold.</p> </div> )} </div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// --- Component definitions (MetricCard, InfoRow, ComplexityBar, DuplicatePairRow - UNCHANGED) ---
function MetricCard({ icon, label, value, color, badge, info, tooltipPosition = 'right' }) { /* ... */
  const colorClasses = { blue: 'bg-blue-100 text-blue-600', yellow: 'bg-yellow-100 text-yellow-600', purple: 'bg-purple-100 text-purple-600', red: 'bg-red-100 text-red-600', green: 'bg-green-100 text-green-600', }; return ( <div className="bg-slate-50 rounded-lg p-5 border border-slate-200"> <div className={`inline-flex p-2 rounded-lg ${colorClasses[color]} mb-3`}>{icon}</div> <div className="flex items-center gap-2 text-sm text-slate-600 mb-1"> <span>{label}</span> {info && (<Tooltip info={info} position={tooltipPosition}><Info className="w-4 h-4 text-slate-400 hover:text-slate-600 transition-colors" /></Tooltip>)} </div> <div className={`text-2xl font-bold text-slate-800 ${badge ? `inline-block px-3 py-1 rounded-lg ${badge}` : ''}`}>{value}</div> </div> );
}
function InfoRow({ label, value, valueClass = 'text-slate-800', info }) { /* ... */
 return ( <div className="flex justify-between items-center"> <div className="flex items-center gap-2"> <span className="text-sm text-slate-600">{label}</span> {info && (<Tooltip info={info}><Info className="w-3.5 h-3.5 text-slate-400 hover:text-slate-600 transition-colors" /></Tooltip>)} </div> <span className={`font-semibold ${valueClass}`}>{value}</span> </div> );
}
function ComplexityBar({ label, value, total, color }) { /* ... */
  const percentage = total > 0 ? (value / total) * 100 : 0; return ( <div> <div className="flex justify-between items-center mb-1"> <span className="text-sm text-slate-600">{label}</span> <span className="text-sm font-semibold text-slate-800">{value}</span> </div> <div className="w-full bg-slate-200 rounded-full h-2"> <div className={`${color} h-2 rounded-full transition-all`} style={{ width: `${percentage}%` }} /> </div> </div> );
}
function DuplicatePairRow({ item }) { /* ... */
  const similarityValue = item?.similarity ?? 0; const similarityPercentage = (similarityValue * 100).toFixed(1); let colorClass = 'bg-yellow-100 text-yellow-800'; if (similarityValue > 0.95) colorClass = 'bg-red-100 text-red-800'; return ( <div className="p-3 bg-white rounded border border-slate-200"> <div className="flex justify-between items-center mb-2"> <span className="text-sm text-slate-700 font-mono truncate flex-1" title={item?.file_a ?? ''}>{item?.file_a ?? 'N/A'}</span> <span className={`ml-3 px-3 py-1 ${colorClass} rounded-full text-sm font-medium whitespace-nowrap`}>{similarityPercentage}%</span> </div> <div className="flex justify-between items-center"> <span className="text-sm text-slate-700 font-mono truncate flex-1" title={item?.file_b ?? ''}>{item?.file_b ?? 'N/A'}</span> </div> </div> );
}

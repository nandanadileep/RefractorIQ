import React, { useState } from 'react';
// --- NEW --- (Added CopyCheck icon)
import { Search, Github, AlertCircle, CheckCircle, TrendingUp, GitBranch, FileCode, Zap, Info, Package, TestTube, CopyCheck } from 'lucide-react';

// Metric definitions and explanations
const METRIC_INFO = {
  loc: {
    title: "Lines of Code",
    description: "Total number of code lines excluding comments and blank lines. Measured using AST parsing.",
    interpretation: "Lower is often better for maintainability. Industry average: 10,000-50,000 LOC per project."
  },
  todos: {
    title: "TODOs/FIXMEs/HACKs",
    description: "Count of TODO, FIXME, and HACK comments in the codebase indicating pending work or technical shortcuts.",
    interpretation: "Lower is better. High counts may indicate incomplete features or deferred refactoring."
  },
  avgComplexity: {
    title: "Average Cyclomatic Complexity",
    description: "Average complexity across all functions. Measures the number of independent paths through code.",
    interpretation: "1-5: Simple, 6-10: Moderate, 11-20: Complex, 21+: Very Complex. Lower is better for maintainability."
  },
  debtScore: {
    title: "Technical Debt Score",
    description: "Composite score calculated from TODOs (×5), complexity (×2), and LOC (÷1000). Higher scores indicate more technical debt.",
    interpretation: "<50: Low debt, 50-100: Moderate, 100-200: High, 200+: Critical. Lower is better."
  },
  totalFunctions: {
    title: "Total Functions",
    description: "Total count of all functions and methods across the codebase including Python functions, JS/TS functions, arrow functions, and class methods.",
    interpretation: "Indicates codebase size and modularity. No strict good/bad threshold."
  },
  filesAnalyzed: {
    title: "Files Analyzed",
    description: "Number of source code files successfully parsed and analyzed (.py, .js, .ts, .java).",
    interpretation: "Should match expected file count. Lower than expected may indicate parsing issues."
  },
  maxComplexity: {
    title: "Maximum Complexity",
    description: "Highest cyclomatic complexity value found in any single function.",
    interpretation: "Values >20 indicate functions that should be refactored. Ideal: <10"
  },
  minComplexity: {
    title: "Minimum Complexity",
    description: "Lowest cyclomatic complexity value found in any single function.",
    interpretation: "Usually 1 for simple functions. Indicates simplest code unit."
  },
  totalFiles: {
    title: "Total Files",
    description: "Total number of source code files included in dependency analysis.",
    interpretation: "Indicates project size. More files require better organization."
  },
  depFunctions: {
    title: "External Dependencies",
    description: "Count of third-party libraries and external modules imported by the codebase from npm, PyPI, Maven, etc.",
    interpretation: "Monitor for security and maintenance. Each dependency is a potential risk vector. Fewer dependencies = less complexity."
  },
  classes: {
    title: "Total Classes",
    description: "Number of class definitions found across the codebase.",
    interpretation: "Indicates OOP usage. Higher doesn't mean better - depends on design approach."
  },
  circularDeps: {
    title: "Circular Dependencies",
    description: "Number of circular dependency chains detected where files depend on each other in a cycle.",
    interpretation: "0 is ideal. Any circular dependencies should be refactored to prevent maintenance issues."
  },
  excludeThirdParty: {
    title: "Exclude Third-Party Libraries",
    description: "When enabled, excludes common third-party library directories (node_modules, venv, site-packages, vendor, etc.) from analysis. On the 'Dependencies' tab, this also hides externally imported libraries.",
    interpretation: "Enable to focus on your code. Note: Most repos .gitignore these folders, so 'Code Metrics' (like LOC) may not change. The 'Dependencies' tab will still update to hide/show external imports."
  },
  excludeTests: {
    title: "Exclude Test Files",
    description: "When enabled, excludes files matching common test patterns (e.g., _test.py, .spec.js, test_*, tests/) from all analysis.",
    interpretation: "Enable this to focus on your application's production code and get a cleaner dependency graph. Disable to include tests in the metrics."
  },
  // --- NEW ---
  duplicatePairs: {
    title: "Duplicate Pairs Found",
    description: "Number of pairs of files found that are considered duplicates based on content similarity (default threshold: 85%).",
    interpretation: "Uses MinHash (datasketch) to find Jaccard similarity. High numbers of duplicates can indicate copy-paste code and poor abstraction."
  },
  // --- NEW ---
  duplicationFilesAnalyzed: {
    title: "Files Analyzed for Duplication",
    description: "Number of files processed by the duplication engine.",
    interpretation: "This number may match 'Files Analyzed' in Code Metrics, depending on exclusions."
  }
};

function Tooltip({ info, children, position = 'right' }) {
  const [show, setShow] = useState(false);

  const getPositionClasses = () => {
    if (position === 'left') {
      return 'right-full mr-3 top-1/2 -translate-y-1/2';
    }
    return 'left-full ml-3 top-1/2 -translate-y-1/2';
  };

  const getArrowClasses = () => {
    if (position === 'left') {
      return '-right-1.5 top-1/2 -translate-y-1/2';
    }
    return '-left-1.5 top-1/2 -translate-y-1/2';
  };

  return (
    <div className="relative inline-block">
      <div 
        onMouseEnter={() => setShow(true)}
        onMouseLeave={() => setShow(false)}
        className="cursor-help"
      >
        {children}
      </div>
      
      {show && (
        <div className={`absolute z-50 w-80 p-4 bg-slate-900 text-white rounded-lg shadow-xl pointer-events-none ${getPositionClasses()}`}>
          <div className={`absolute w-3 h-3 bg-slate-900 transform rotate-45 ${getArrowClasses()}`}></div>
          <h4 className="font-semibold text-sm mb-2 text-blue-300">{info.title}</h4>
          <p className="text-xs text-slate-300 mb-2">{info.description}</p>
          <p className="text-xs text-slate-400 italic">{info.interpretation}</p>
        </div>
      )}
    </div>
  );
}

export default function RefractorIQDashboard() {
  const [repoUrl, setRepoUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const [analysisData, setAnalysisData] = useState(null);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState('metrics');
  const [excludeThirdParty, setExcludeThirdParty] = useState(true);
  const [excludeTests, setExcludeTests] = useState(true);

  const BACKEND_URL = 'https://fluffy-fortnight-pjr95546qg936qrg-8000.app.github.dev';

  const analyzeRepo = async () => {
    if (!repoUrl.trim()) {
      setError('Please enter a repository URL');
      return;
    }

    setLoading(true);
    setError(null);
    setAnalysisData(null);

    try {
      // Fetch URL calls /analyze/full, which now includes duplication_metrics
      const response = await fetch(
        `${BACKEND_URL}/analyze/full?repo_url=${encodeURIComponent(repoUrl)}&exclude_third_party=${excludeThirdParty}&exclude_tests=${excludeTests}`
      );
      
      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.error || 'Analysis failed');
      }

      const data = await response.json();
      setAnalysisData(data);
    } catch (err) {
      setError(err.message || 'Failed to analyze repository');
    } finally {
      setLoading(false);
    }
  };

  const getComplexityColor = (complexity) => {
    if (complexity <= 5) return 'text-green-600';
    if (complexity <= 10) return 'text-yellow-600';
    if (complexity <= 20) return 'text-orange-600';
    return 'text-red-600';
  };

  const getDebtScoreColor = (score) => {
    if (score < 50) return 'bg-green-100 text-green-800';
    if (score < 100) return 'bg-yellow-100 text-yellow-800';
    if (score < 200) return 'bg-orange-100 text-orange-800';
    return 'bg-red-100 text-red-800';
  };

  const normalizeValue = (value, metricKey) => {
    if (value === undefined || value === null) return 'N/A';
    if (metricKey === 'loc' && value > 1000) {
      return `${(value / 1000).toFixed(1)}K`;
    }
    return value.toLocaleString();
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100">
      {/* Header */}
      <div className="bg-white shadow-sm border-b border-slate-200">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="bg-gradient-to-br from-blue-500 to-purple-600 p-2 rounded-lg">
              <FileCode className="w-6 h-6 text-white" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-slate-800">RefractorIQ</h1>
              <p className="text-sm text-slate-500">Code Quality Analysis Dashboard</p>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 py-8">
        {/* Search Section */}
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 mb-6">
          <div className="flex gap-3 mb-4">
            <div className="flex-1 relative">
              <Github className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" />
              <input
                type="text"
                value={repoUrl}
                onChange={(e) => setRepoUrl(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && analyzeRepo()}
                placeholder="Enter GitHub repository URL (e.g., https://github.com/user/repo)"
                className="w-full pl-11 pr-4 py-3 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none"
              />
            </div>
            <button
              onClick={analyzeRepo}
              disabled={loading}
              className="px-6 py-3 bg-gradient-to-r from-blue-500 to-purple-600 text-white rounded-lg font-medium hover:shadow-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            >
              {loading ? (
                <>
                  <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  Analyzing...
                </>
              ) : (
                <>
                  <Search className="w-5 h-5" />
                  Analyze
                </>
              )}
            </button>
          </div>

          {/* Toggles Wrapper */}
          <div className="space-y-3">
            {/* Third-Party Toggle */}
            <div className="flex items-center gap-3 p-4 bg-slate-50 rounded-lg border border-slate-200">
              <label className="flex items-center gap-3 cursor-pointer flex-1">
                <div className="relative">
                  <input
                    type="checkbox"
                    checked={excludeThirdParty}
                    onChange={(e) => setExcludeThirdParty(e.target.checked)}
                    className="sr-only peer"
                  />
                  <div className="w-11 h-6 bg-slate-300 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
                </div>
                <div className="flex items-center gap-2">
                  <Package className="w-5 h-5 text-slate-600" />
                  <span className="text-sm font-medium text-slate-700">
                    Exclude Third-Party Libraries
                  </span>
                </div>
              </label>
              <Tooltip info={METRIC_INFO.excludeThirdParty} position="left">
                <Info className="w-5 h-5 text-slate-400 hover:text-slate-600 transition-colors cursor-help" />
              </Tooltip>
            </div>
            
            {/* Test File Toggle */}
            <div className="flex items-center gap-3 p-4 bg-slate-50 rounded-lg border border-slate-200">
              <label className="flex items-center gap-3 cursor-pointer flex-1">
                <div className="relative">
                  <input
                    type="checkbox"
                    checked={excludeTests}
                    onChange={(e) => setExcludeTests(e.target.checked)}
                    className="sr-only peer"
                  />
                  <div className="w-11 h-6 bg-slate-300 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
                </div>
                <div className="flex items-center gap-2">
                  <TestTube className="w-5 h-5 text-slate-600" />
                  <span className="text-sm font-medium text-slate-700">
                    Exclude Test Files
                  </span>
                </div>
              </label>
              <Tooltip info={METRIC_INFO.excludeTests} position="left">
                <Info className="w-5 h-5 text-slate-400 hover:text-slate-600 transition-colors cursor-help" />
              </Tooltip>
            </div>
          </div>
          
          {error && (
            <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-lg flex items-center gap-3">
              <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0" />
              <p className="text-red-800">{error}</p>
            </div>
          )}
        </div>

        {/* Results Section */}
        {analysisData && (
          <div className="space-y-6">
            {/* Repository Info */}
            <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <CheckCircle className="w-6 h-6 text-green-600" />
                  <div>
                    <h2 className="text-xl font-bold text-slate-800">Analysis Complete</h2>
                    <p className="text-slate-600 break-all">{analysisData.repository}</p>
                  </div>
                </div>
                <div className="flex flex-col items-end gap-1">
                  {analysisData.excluded_third_party && (
                    <div className="flex items-center gap-2 px-3 py-1.5 bg-blue-50 border border-blue-200 rounded-lg">
                      <Package className="w-4 h-4 text-blue-600" />
                      <span className="text-xs font-medium text-blue-700">Third-party excluded</span>
                    </div>
                  )}
                  {analysisData.excluded_tests && (
                    <div className="flex items-center gap-2 px-3 py-1.5 bg-green-50 border border-green-200 rounded-lg">
                      <TestTube className="w-4 h-4 text-green-600" />
                      <span className="text-xs font-medium text-green-700">Tests excluded</span>
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* --- NEW TABS --- */}
            <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
              <div className="flex border-b border-slate-200">
                <button
                  onClick={() => setActiveTab('metrics')}
                  className={`flex-1 px-6 py-4 font-medium transition-colors ${
                    activeTab === 'metrics'
                      ? 'bg-blue-50 text-blue-600 border-b-2 border-blue-600'
                      : 'text-slate-600 hover:bg-slate-50'
                  }`}
                >
                  Code Metrics
                </button>
                <button
                  onClick={() => setActiveTab('dependencies')}
                  className={`flex-1 px-6 py-4 font-medium transition-colors ${
                    activeTab === 'dependencies'
                      ? 'bg-blue-50 text-blue-600 border-b-2 border-blue-600'
                      : 'text-slate-600 hover:bg-slate-50'
                  }`}
                >
                  Dependencies
                </button>
                {/* --- NEW DUPLICATION TAB BUTTON --- */}
                <button
                  onClick={() => setActiveTab('duplication')}
                  className={`flex-1 px-6 py-4 font-medium transition-colors ${
                    activeTab === 'duplication'
                      ? 'bg-blue-50 text-blue-600 border-b-2 border-blue-600'
                      : 'text-slate-600 hover:bg-slate-50'
                  }`}
                >
                  Duplication
                </button>
              </div>

              <div className="p-6">
                {activeTab === 'metrics' && (
                  <div className="space-y-6">
                    {/* Key Metrics Grid */}
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                      <MetricCard
                        icon={<FileCode className="w-5 h-5" />}
                        label="Lines of Code"
                        value={normalizeValue(analysisData.code_metrics.LOC, 'loc')}
                        color="blue"
                        info={METRIC_INFO.loc}
                      />
                      <MetricCard
                        icon={<AlertCircle className="w-5 h-5" />}
                        label="TODOs/FIXMEs"
                        value={analysisData.code_metrics.TODOs_FIXME_HACK}
                        color="yellow"
                        info={METRIC_INFO.todos}
                      />
                      <MetricCard
                        icon={<TrendingUp className="w-5 h-5" />}
                        label="Avg Complexity"
                        value={analysisData.code_metrics.AvgCyclomaticComplexity}
                        color="purple"
                        info={METRIC_INFO.avgComplexity}
                      />
                      <MetricCard
                        icon={<Zap className="w-5 h-5" />}
                        label="Debt Score"
                        value={analysisData.code_metrics.DebtScore}
                        color="red"
                        badge={getDebtScoreColor(analysisData.code_metrics.DebtScore)}
                        info={METRIC_INFO.debtScore}
                        tooltipPosition="left"
                      />
                    </div>

                    {/* Detailed Metrics */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                      <div className="bg-slate-50 rounded-lg p-5 border border-slate-200">
                        <h3 className="font-semibold text-slate-800 mb-4">Function Analysis</h3>
                        <div className="space-y-3">
                          <InfoRow 
                            label="Total Functions" 
                            value={analysisData.code_metrics.TotalFunctions}
                            info={METRIC_INFO.totalFunctions}
                          />
                          <InfoRow 
                            label="Files Analyzed" 
                            value={analysisData.code_metrics.FilesAnalyzed}
                            info={METRIC_INFO.filesAnalyzed}
                          />
                          <InfoRow 
                            label="Max Complexity" 
                            value={analysisData.code_metrics.MaxComplexity}
                            valueClass={getComplexityColor(analysisData.code_metrics.MaxComplexity)}
                            info={METRIC_INFO.maxComplexity}
                          />
                          <InfoRow 
                            label="Min Complexity" 
                            value={analysisData.code_metrics.MinComplexity}
                            valueClass="text-green-600"
                            info={METRIC_INFO.minComplexity}
                          />
                        </div>
                      </div>

                      <div className="bg-slate-50 rounded-lg p-5 border border-slate-200">
                        <h3 className="font-semibold text-slate-800 mb-4">Complexity Distribution</h3>
                        <div className="space-y-3">
                          <ComplexityBar 
                            label="Low (1-5)" 
                            value={analysisData.code_metrics.ComplexityDistribution.low}
                            total={analysisData.code_metrics.TotalFunctions}
                            color="bg-green-500"
                          />
                          <ComplexityBar 
                            label="Medium (6-10)" 
                            value={analysisData.code_metrics.ComplexityDistribution.medium}
                            total={analysisData.code_metrics.TotalFunctions}
                            color="bg-yellow-500"
                          />
                          <ComplexityBar 
                            label="High (11-20)" 
                            value={analysisData.code_metrics.ComplexityDistribution.high}
                            total={analysisData.code_metrics.TotalFunctions}
                            color="bg-orange-500"
                          />
                          <ComplexityBar 
                            label="Very High (21+)" 
                            value={analysisData.code_metrics.ComplexityDistribution.very_high}
                            total={analysisData.code_metrics.TotalFunctions}
                            color="bg-red-500"
                          />
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                {activeTab === 'dependencies' && (
                  <div className="space-y-6">
                    {/* Dependency Stats */}
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                      <MetricCard
                        icon={<FileCode className="w-5 h-5" />}
                        label="Total Files"
                        value={analysisData.dependency_metrics.total_files}
                        color="blue"
                        info={METRIC_INFO.totalFiles}
                      />
                      <MetricCard
                        icon={<GitBranch className="w-5 h-5" />}
                        label="External Dependencies"
                        value={analysisData.dependency_metrics.total_external_dependencies}
                        color="green"
                        info={METRIC_INFO.depFunctions}
                      />
                      <MetricCard
                        icon={<GitBranch className="w-5 h-5" />}
                        label="Classes"
                        value={analysisData.dependency_metrics.total_classes}
                        color="purple"
                        info={METRIC_INFO.classes}
                      />
                      <MetricCard
                        icon={<AlertCircle className="w-5 h-5" />}
                        label="Circular Dependencies"
                        value={analysisData.dependency_metrics.circular_dependencies}
                        color="red"
                        info={METRIC_INFO.circularDeps}
                        tooltipPosition="left"
                      />
                    </div>

                    {/* Most Dependent Files */}
                    {analysisData.dependency_metrics.most_dependent_files.length > 0 && (
                      <div className="bg-slate-50 rounded-lg p-5 border border-slate-200">
                        <h3 className="font-semibold text-slate-800 mb-4">Most Dependent Files</h3>
                        <div className="space-y-2">
                          {analysisData.dependency_metrics.most_dependent_files.map((item, idx) => (
                            <div key={idx} className="flex justify-between items-center p-3 bg-white rounded border border-slate-200">
                              <span className="text-sm text-slate-700 font-mono truncate flex-1">{item.file}</span>
                              <span className="ml-3 px-3 py-1 bg-blue-100 text-blue-800 rounded-full text-sm font-medium">
                                {item.dependencies} deps
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Most Depended On Files */}
                    {analysisData.dependency_metrics.most_depended_on_files.length > 0 && (
                      <div className="bg-slate-50 rounded-lg p-5 border border-slate-200">
                        <h3 className="font-semibold text-slate-800 mb-4">Most Depended On Files</h3>
                        <div className="space-y-2">
                          {analysisData.dependency_metrics.most_depended_on_files.map((item, idx) => (
                            <div key={idx} className="flex justify-between items-center p-3 bg-white rounded border border-slate-200">
                              <span className="text-sm text-slate-700 font-mono truncate flex-1">{item.file}</span>
                              <span className="ml-3 px-3 py-1 bg-purple-100 text-purple-800 rounded-full text-sm font-medium">
                                {item.dependents} dependents
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
                
                {/* --- NEW DUPLICATION TAB PANEL --- */}
                {activeTab === 'duplication' && (
                  <div className="space-y-6">
                    {/* Duplication Stats */}
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                      <MetricCard
                        icon={<CopyCheck className="w-5 h-5" />}
                        label="Duplicate Pairs Found"
                        value={analysisData.duplication_metrics?.duplicate_pairs_found ?? 'N/A'}
                        color="yellow"
                        info={METRIC_INFO.duplicatePairs}
                      />
                      <MetricCard
                        icon={<FileCode className="w-5 h-5" />}
                        label="Files Analyzed"
                        value={analysisData.duplication_metrics?.files_analyzed ?? 'N/A'}
                        color="blue"
                        info={METRIC_INFO.duplicationFilesAnalyzed}
                      />
                    </div>
                    
                    {/* Error Display */}
                    {analysisData.duplication_metrics?.error && (
                      <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-lg flex items-center gap-3">
                        <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0" />
                        <p className="text-red-800">
                          Duplication analysis failed: {analysisData.duplication_metrics.error}
                        </p>
                      </div>
                    )}

                    {/* Duplicate Pairs List */}
                    {(analysisData.duplication_metrics?.duplicates?.length ?? 0) > 0 && (
                      <div className="bg-slate-50 rounded-lg p-5 border border-slate-200">
                        <h3 className="font-semibold text-slate-800 mb-4">
                          Duplicate File Pairs (Threshold: {analysisData.duplication_metrics.similarity_threshold * 100}%)
                        </h3>
                        <div className="space-y-2">
                          {analysisData.duplication_metrics.duplicates.map((item, idx) => (
                            <DuplicatePairRow key={idx} item={item} />
                          ))}
                        </div>
                      </div>
                    )}
                    
                    {/* No Duplicates Found Message */}
                    {(!analysisData.duplication_metrics || analysisData.duplication_metrics?.duplicates?.length === 0) && !analysisData.duplication_metrics?.error && (
                      <div className="text-center p-6 bg-slate-50 rounded-lg border border-slate-200">
                        <CheckCircle className="w-12 h-12 text-green-500 mx-auto mb-3" />
                        <h4 className="font-semibold text-slate-700">No Duplicates Found</h4>
                        <p className="text-sm text-slate-500">
                          No file pairs met the {analysisData.duplication_metrics.similarity_threshold * 100}% similarity threshold.
                        </p>
                      </div>
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

function MetricCard({ icon, label, value, color, badge, info, tooltipPosition = 'right' }) {
  const colorClasses = {
    blue: 'bg-blue-100 text-blue-600',
    yellow: 'bg-yellow-100 text-yellow-600',
    purple: 'bg-purple-100 text-purple-600',
    red: 'bg-red-100 text-red-600',
    green: 'bg-green-100 text-green-600',
  };

  return (
    <div className="bg-slate-50 rounded-lg p-5 border border-slate-200">
      <div className={`inline-flex p-2 rounded-lg ${colorClasses[color]} mb-3`}>
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
      <div className={`text-2xl font-bold text-slate-800 ${badge ? `inline-block px-3 py-1 rounded-lg ${badge}` : ''}`}>
        {value}
      </div>
    </div>
  );
}

function InfoRow({ label, value, valueClass = 'text-slate-800', info }) {
  return (
    <div className="flex justify-between items-center">
      <div className="flex items-center gap-2">
        <span className="text-sm text-slate-600">{label}</span>
        {info && (
          <Tooltip info={info}>
            <Info className="w-3.5 h-3.5 text-slate-400 hover:text-slate-600 transition-colors" />
          </Tooltip>
        )}
      </div>
      <span className={`font-semibold ${valueClass}`}>{value}</span>
    </div>
  );
}

function ComplexityBar({ label, value, total, color }) {
  const percentage = total > 0 ? (value / total) * 100 : 0;
  
  return (
    <div>
      <div className="flex justify-between items-center mb-1">
        <span className="text-sm text-slate-600">{label}</span>
        <span className="text-sm font-semibold text-slate-800">{value}</span>
      </div>
      <div className="w-full bg-slate-200 rounded-full h-2">
        <div
          className={`${color} h-2 rounded-full transition-all`}
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  );
}

// --- NEW COMPONENT ---
// Renders a single row for a duplicate pair
function DuplicatePairRow({ item }) {
  const similarityPercentage = (item.similarity * 100).toFixed(1);
  let colorClass = 'bg-yellow-100 text-yellow-800';
  if (item.similarity > 0.95) {
    colorClass = 'bg-red-100 text-red-800';
  }

  return (
    <div className="p-3 bg-white rounded border border-slate-200">
      <div className="flex justify-between items-center mb-2">
        <span className="text-sm text-slate-700 font-mono truncate flex-1">{item.file_a}</span>
        <span className={`ml-3 px-3 py-1 ${colorClass} rounded-full text-sm font-medium`}>
          {similarityPercentage}%
        </span>
      </div>
      <div className="flex justify-between items-center">
        <span className="text-sm text-slate-700 font-mono truncate flex-1">{item.file_b}</span>
      </div>
    </div>
  );
}


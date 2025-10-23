import React, { useState } from 'react';
import { Search, Github, AlertCircle, CheckCircle, TrendingUp, GitBranch, FileCode, Zap } from 'lucide-react';

export default function RefractorIQDashboard() {
  const [repoUrl, setRepoUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const [analysisData, setAnalysisData] = useState(null);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState('metrics');

  const BACKEND_URL = 'https://fluffy-fortnight-pjr95546qg936qrg-8000.app.github.dev'; // GitHub Codespaces backend URL

  const analyzeRepo = async () => {
    if (!repoUrl.trim()) {
      setError('Please enter a repository URL');
      return;
    }

    setLoading(true);
    setError(null);
    setAnalysisData(null);

    try {
      const response = await fetch(
        `${BACKEND_URL}/analyze/full?repo_url=${encodeURIComponent(repoUrl)}`
      );
      
      if (!response.ok) {
        throw new Error('Analysis failed');
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
          <div className="flex gap-3">
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
              <div className="flex items-center gap-3 mb-2">
                <CheckCircle className="w-6 h-6 text-green-600" />
                <h2 className="text-xl font-bold text-slate-800">Analysis Complete</h2>
              </div>
              <p className="text-slate-600 break-all">{analysisData.repository}</p>
            </div>

            {/* Tabs */}
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
              </div>

              <div className="p-6">
                {activeTab === 'metrics' && (
                  <div className="space-y-6">
                    {/* Key Metrics Grid */}
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                      <MetricCard
                        icon={<FileCode className="w-5 h-5" />}
                        label="Lines of Code"
                        value={analysisData.code_metrics.LOC.toLocaleString()}
                        color="blue"
                      />
                      <MetricCard
                        icon={<AlertCircle className="w-5 h-5" />}
                        label="TODOs/FIXMEs"
                        value={analysisData.code_metrics.TODOs_FIXME_HACK}
                        color="yellow"
                      />
                      <MetricCard
                        icon={<TrendingUp className="w-5 h-5" />}
                        label="Avg Complexity"
                        value={analysisData.code_metrics.AvgCyclomaticComplexity}
                        color="purple"
                      />
                      <MetricCard
                        icon={<Zap className="w-5 h-5" />}
                        label="Debt Score"
                        value={analysisData.code_metrics.DebtScore}
                        color="red"
                        badge={getDebtScoreColor(analysisData.code_metrics.DebtScore)}
                      />
                    </div>

                    {/* Detailed Metrics */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                      <div className="bg-slate-50 rounded-lg p-5 border border-slate-200">
                        <h3 className="font-semibold text-slate-800 mb-4">Function Analysis</h3>
                        <div className="space-y-3">
                          <InfoRow label="Total Functions" value={analysisData.code_metrics.TotalFunctions} />
                          <InfoRow label="Files Analyzed" value={analysisData.code_metrics.FilesAnalyzed} />
                          <InfoRow 
                            label="Max Complexity" 
                            value={analysisData.code_metrics.MaxComplexity}
                            valueClass={getComplexityColor(analysisData.code_metrics.MaxComplexity)}
                          />
                          <InfoRow 
                            label="Min Complexity" 
                            value={analysisData.code_metrics.MinComplexity}
                            valueClass="text-green-600"
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
                      />
                      <MetricCard
                        icon={<GitBranch className="w-5 h-5" />}
                        label="Functions"
                        value={analysisData.dependency_metrics.total_functions}
                        color="green"
                      />
                      <MetricCard
                        icon={<GitBranch className="w-5 h-5" />}
                        label="Classes"
                        value={analysisData.dependency_metrics.total_classes}
                        color="purple"
                      />
                      <MetricCard
                        icon={<AlertCircle className="w-5 h-5" />}
                        label="Circular Dependencies"
                        value={analysisData.dependency_metrics.circular_dependencies}
                        color="red"
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
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function MetricCard({ icon, label, value, color, badge }) {
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
      <div className="text-sm text-slate-600 mb-1">{label}</div>
      <div className={`text-2xl font-bold text-slate-800 ${badge ? `inline-block px-3 py-1 rounded-lg ${badge}` : ''}`}>
        {value}
      </div>
    </div>
  );
}

function InfoRow({ label, value, valueClass = 'text-slate-800' }) {
  return (
    <div className="flex justify-between items-center">
      <span className="text-sm text-slate-600">{label}</span>
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


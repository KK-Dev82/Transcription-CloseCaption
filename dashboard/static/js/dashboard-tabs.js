/**
 * Dashboard Tabs Controller
 * Handles tab switching and coordination
 */

// Tab switching
function switchTab(tabName) {
    // Auto-refresh Overview tab when switching to it
    if (tabName === 'overview' && typeof refreshOverviewServer === 'function') {
        // Small delay to ensure tab is visible
        setTimeout(() => {
            const currentServer = window.currentOverviewServer || '4000-ada-sc';
            if (typeof manualRefreshOverview === 'function') {
                // Clear cache to force reload
                if (window.paginationState && window.paginationState[currentServer]) {
                    window.paginationState[currentServer].allTasks = [];
                    window.paginationState[currentServer].currentPage = 1;
                }
                manualRefreshOverview();
            } else if (typeof refreshOverviewServer === 'function') {
                refreshOverviewServer(currentServer);
            }
        }, 100);
    }
    // Hide all tabs
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.classList.remove('active');
    });
    document.querySelectorAll('.tab-button').forEach(btn => {
        btn.classList.remove('active');
    });

    // Show selected tab
    const tabContent = document.getElementById(`tab-${tabName}`);
    const tabButton = document.getElementById(`tab-${tabName}-btn`);
    if (tabContent) tabContent.classList.add('active');
    if (tabButton) tabButton.classList.add('active');

    // Start appropriate refresh
    if (tabName === 'overview') {
        // Stop other tabs
        if (typeof stopTestRefresh === 'function') {
            stopTestRefresh();
        }
        if (typeof stopMonitorRefresh === 'function') {
            stopMonitorRefresh();
        }
        if (typeof stopMonitoringTab === 'function') {
            stopMonitoringTab();
        }
        // Load initial server data (no auto-refresh)
        if (typeof selectOverviewServer === 'function') {
            selectOverviewServer('4000-ada-sc');
        }
    } else if (tabName === 'test') {
        // Stop other tabs
        if (typeof stopOverviewRefresh === 'function') {
            stopOverviewRefresh();
        }
        if (typeof stopMonitorRefresh === 'function') {
            stopMonitorRefresh();
        }
        if (typeof stopMonitoringTab === 'function') {
            stopMonitoringTab();
        }
        const testResultsSection = document.getElementById('testResultsSection');
        if (testResultsSection && testResultsSection.style.display !== 'none') {
            if (typeof startTestRefresh === 'function') {
                startTestRefresh();
            }
        }
    } else if (tabName === 'monitoring') {
        // Stop other tabs
        if (typeof stopOverviewRefresh === 'function') {
            stopOverviewRefresh();
        }
        if (typeof stopTestRefresh === 'function') {
            stopTestRefresh();
        }
        if (typeof stopMonitorRefresh === 'function') {
            stopMonitorRefresh();
        }
        // Select default server and start monitoring tab (only refreshes itself)
        if (typeof selectMonitoringServer === 'function') {
            selectMonitoringServer('4000-ada-sc');
        }
        if (typeof startMonitoringTab === 'function') {
            startMonitoringTab();
        }
    } else if (tabName === 'monitor') {
        // Stop other tabs
        if (typeof stopOverviewRefresh === 'function') {
            stopOverviewRefresh();
        }
        if (typeof stopTestRefresh === 'function') {
            stopTestRefresh();
        }
        if (typeof stopMonitoringTab === 'function') {
            stopMonitoringTab();
        }
        if (typeof loadPreviousResults === 'function') {
            loadPreviousResults();
        }
    } else if (tabName === 'live-streaming') {
        // Stop other tabs
        if (typeof stopOverviewRefresh === 'function') {
            stopOverviewRefresh();
        }
        if (typeof stopTestRefresh === 'function') {
            stopTestRefresh();
        }
        if (typeof stopMonitoringTab === 'function') {
            stopMonitoringTab();
        }
        if (typeof stopMonitorRefresh === 'function') {
            stopMonitorRefresh();
        }
        // Initialize HLS player if not already initialized
        if (typeof initializeHLSPlayer === 'function') {
            setTimeout(() => {
                initializeHLSPlayer();
            }, 100);
        }
    }
}

// Export functions
window.switchTab = switchTab;

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    // Set up test form listeners
    document.getElementById('testVideo')?.addEventListener('change', () => {
        if (typeof updateTestStartButton === 'function') {
            updateTestStartButton();
        }
    });
    document.getElementById('testCount')?.addEventListener('input', () => {
        if (typeof updateTestStartButton === 'function') {
            updateTestStartButton();
        }
    });
    
    // Start with Overview tab
    switchTab('overview');
});

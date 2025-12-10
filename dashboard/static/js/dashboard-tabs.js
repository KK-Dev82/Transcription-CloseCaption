/**
 * Dashboard Tabs Controller
 * Handles tab switching and coordination
 */

// Tab switching
function switchTab(tabName) {
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
        if (typeof startOverviewRefresh === 'function') {
            startOverviewRefresh();
        }
        if (typeof stopTestRefresh === 'function') {
            stopTestRefresh();
        }
    } else if (tabName === 'test') {
        if (typeof stopOverviewRefresh === 'function') {
            stopOverviewRefresh();
        }
        const testResultsSection = document.getElementById('testResultsSection');
        if (testResultsSection && testResultsSection.style.display !== 'none') {
            if (typeof startTestRefresh === 'function') {
                startTestRefresh();
            }
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

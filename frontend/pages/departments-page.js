window.DashboardPageModules = window.DashboardPageModules || {};

window.DashboardPageModules.departments = {
    sectionId: 'departments-section',

    render() {
        if (typeof renderDepartmentComparison === 'function') {
            renderDepartmentComparison();
        }
    },
};

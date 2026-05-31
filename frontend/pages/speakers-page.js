window.DashboardPageModules = window.DashboardPageModules || {};

window.DashboardPageModules.speakers = {
    sectionId: 'speakers-section',

    render() {
        if (typeof renderSpeakers === 'function') {
            renderSpeakers((state.analytics && state.analytics.speakerStats) || []);
        }
    },
};

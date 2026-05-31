window.DashboardPageModules = window.DashboardPageModules || {};

window.DashboardPageModules.nlp = {
    sectionId: 'nlp-section',

    render() {
        const analytics = state.analytics || {};
        if (typeof renderDeepAnalysis === 'function') renderDeepAnalysis(analytics.deepAnalysis || null);
        if (typeof renderSentiment === 'function') renderSentiment(analytics.sentiment || []);
        if (typeof renderKeywords === 'function') renderKeywords(analytics.keywords || []);
    },
};

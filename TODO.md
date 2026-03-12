# DataLens — TODO List (Remaining Improvements)

## 🟡 Important Improvements

### 1. Better Fuzzy Matching for Department Names
- [ ] Current threshold: 65% similarity — may be too aggressive or too loose
- [ ] Test with actual data: "B.E.D" vs "B ED" vs "Education" — should these merge?
- [ ] Consider domain-specific rules: "Btech CSE" and "Btech CSE AIML" should NOT merge (different specializations)
- [ ] Add a UI toggle to show original vs normalized values

### 2. Cross-Tab Improvements
- [ ] Show data labels on bars (the actual avg value)
- [ ] Add a heatmap view option (color intensity = avg rating)
- [ ] Allow user to pick which numeric × categorical combination to visualize

### 3. TF-IDF Keyword Scoring
- [ ] Use TF-IDF scoring to find distinctive words per column (beyond simple frequency)

---

## 🟢 Nice-to-Have Enhancements

### 4. Export Features
- [ ] Export individual charts as PNG images
- [ ] Export full analytics report as PDF
- [ ] Export filtered data as Excel (.xlsx)

### 5. Additional Visualizations
- [ ] Radar/spider chart for multi-dimensional speaker comparison
- [ ] Pie chart for helpfulness question (3 values → perfect for pie)
- [ ] Scatter plot: rating vs sentiment per response
- [ ] Calendar heatmap: response density by date

### 6. Real-Time Filtering with Animation
- [ ] Animate chart transitions when filters change
- [ ] Show loading skeleton while Python processes filter request

### 7. Accessibility
- [ ] Add ARIA labels to interactive elements
- [ ] Keyboard navigation for sidebar
- [ ] High-contrast mode toggle

### 8. Upload History
- [ ] Remember previously uploaded files (localStorage)
- [ ] Quick re-load from history

---

## File-Specific Changes Reference

| File | Todo Items |
|------|-----------|
| `app.py` | #1 (fuzzy threshold), #3 (TF-IDF) |
| `app.js` | #2 (cross-tab labels), #5 (new chart types), #6 (animations) |
| `style.css` | #6 (skeleton loading), #7 (accessibility) |
| `index.html` | #4 (export buttons), #8 (upload history section) |

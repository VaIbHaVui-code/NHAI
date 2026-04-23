const mongoose = require('mongoose');

const SignSchema = new mongoose.Schema({
  sign_id: { type: String },
  sign_type: { type: String, required: true },
  reflectivity_score: { type: Number, required: true },
  status: { type: String, required: true }, // "Pass" or "Fail"
  months_remaining: { type: Number },
  gps: {
    lat: { type: Number, required: true },
    lng: { type: Number, required: true }
  },
  confidence: { type: Number },
  lighting: { type: String },
  timestamp: { type: Date, default: Date.now }
});

module.exports = mongoose.model('Sign', SignSchema);
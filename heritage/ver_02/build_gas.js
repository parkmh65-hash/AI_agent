// build_gas.js - ver_02 GAS HTML/JS Inliner Compiler Script

const fs = require('fs');
const path = require('path');
const uglify = require('uglify-js');

const PROJECTS = [
  {
    name: 'GAS_react (User Client)',
    dir: path.join(__dirname, 'GAS_react'),
    tempJs: path.join(__dirname, 'GAS_react', 'temp_script.js'),
    tempCss: path.join(__dirname, 'GAS_react', 'temp_script.css'),
    outScript: path.join(__dirname, 'GAS_react', 'script.html'),
    outStyle: path.join(__dirname, 'GAS_react', 'style.html'),
  },
  {
    name: 'GAS_react_supvisor (Supervisor Dashboard)',
    dir: path.join(__dirname, 'GAS_react_supvisor'),
    tempJs: path.join(__dirname, 'GAS_react_supvisor', 'temp_script.js'),
    tempCss: path.join(__dirname, 'GAS_react_supvisor', 'temp_script.css'),
    outScript: path.join(__dirname, 'GAS_react_supvisor', 'script.html'),
    outStyle: path.join(__dirname, 'GAS_react_supvisor', 'style.html'),
  }
];

function processProject(p) {
  console.log(`\nProcessing ${p.name}...`);
  
  if (!fs.existsSync(p.tempJs)) {
    console.error(`Error: Temporary JS bundle not found at ${p.tempJs}`);
    return;
  }
  
  // 1. Minify and format JavaScript with 500 max_line_len limit for GAS
  const jsCode = fs.readFileSync(p.tempJs, 'utf-8');
  console.log(`Original JS bundle size: ${jsCode.length} bytes`);
  
  const options = {
    compress: {
      dead_code: true,
      global_defs: {
        DEBUG: false
      }
    },
    output: {
      max_line_len: 500
    }
  };
  
  const result = uglify.minify(jsCode, options);
  if (result.error) {
    console.error(`UglifyJS Error for ${p.name}:`, result.error);
    return;
  }
  
  const formattedJs = `<script>\n${result.code}\n</script>`;
  fs.writeFileSync(p.outScript, formattedJs, 'utf-8');
  console.log(`Saved compiled script template to: ${p.outScript} (${formattedJs.length} bytes)`);
  
  // 2. Compress and wrap stylesheet
  let cssCode = '';
  if (fs.existsSync(p.tempCss)) {
    cssCode = fs.readFileSync(p.tempCss, 'utf-8');
  } else {
    // Fallback if no css generated
    cssCode = '/* No styles bundled */';
  }
  
  // Simple CSS compression (remove spaces and comments)
  const minifiedCss = cssCode
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .replace(/\s+/g, ' ')
    .replace(/\{\s*/g, '{')
    .replace(/\s*\}/g, '}')
    .replace(/;\s*/g, ';')
    .replace(/,\s*/g, ',')
    .trim();
    
  const formattedCss = `<style>\n${minifiedCss}\n</style>`;
  fs.writeFileSync(p.outStyle, formattedCss, 'utf-8');
  console.log(`Saved stylesheet template to: ${p.outStyle} (${formattedCss.length} bytes)`);
  
  // 3. Clean temporary build assets
  try {
    fs.unlinkSync(p.tempJs);
    if (fs.existsSync(p.tempCss)) {
      fs.unlinkSync(p.tempCss);
    }
    console.log(`Cleaned up temporary assets.`);
  } catch (err) {
    console.warn(`Warning cleaning temporary files:`, err);
  }
}

console.log('--- Starting GAS Template Compiler (ver_02) ---');
PROJECTS.forEach(processProject);
console.log('\n--- Compilation successfully completed! ---');

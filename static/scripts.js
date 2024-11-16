let pointA = null;
let pointB = null;
let referenceImage = null;
let sampleImages = [];
let currentSamples = [];

const referenceCanvas = document.getElementById('referenceCanvas');
const refCtx = referenceCanvas.getContext('2d');
const downloadButton = document.getElementById('downloadExcel');

function drawPoint(ctx, x, y, color = 'red', size = 3) {
    ctx.beginPath();
    ctx.arc(x, y, size, 0, 2 * Math.PI);
    ctx.fillStyle = color;
    ctx.fill();
    ctx.strokeStyle = 'white';
    ctx.lineWidth = 1;
    ctx.stroke();
}

function drawLine(ctx, pointA, pointB, color = 'blue') {
    ctx.beginPath();
    ctx.moveTo(pointA.x, pointA.y);
    ctx.lineTo(pointB.x, pointB.y);
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.stroke();
}

async function analyzeLine(pointA, pointB) {
    try {
        for (let i = 0; i < currentSamples.length; i++) {
            const response = await fetch('/analyze_line', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    pointA: pointA,
                    pointB: pointB,
                    sampleIndex: i
                })
            });

            const data = await response.json();
            
            // Update the profile images
            if (data.reference_profile) {
                document.getElementById('refProfileImage').src = data.reference_profile + '?t=' + new Date().getTime();
            }
            
            // Update sample profile
            const sampleProfileImg = document.getElementById(`sampleProfileImage_${i}`);
            if (data.sample_profile && sampleProfileImg) {
                sampleProfileImg.src = data.sample_profile + '?t=' + new Date().getTime();
            }
            
            // Update absorption profile
           // Update absorption profile
const absProfileImg = document.getElementById('combinedAbsProfileImage');
if (data.absorption_profile && absProfileImg) {
    absProfileImg.src = data.absorption_profile + '?t=' + new Date().getTime();
}
        }
        
        downloadButton.style.display = 'block';
    } catch (error) {
        console.error('Analysis error:', error);
    }
}
// For the reference file input
document.querySelector('input[name="reference"]').addEventListener('change', function(e) {
    const file = e.target.files[0];
    const fileName = file ? file.name : 'No file chosen';
    e.target.nextElementSibling.textContent = fileName; // Show the file name
});

// For the sample file input
document.querySelector('input[name="samples"]').addEventListener('change', function(e) {
    const files = e.target.files;
    const fileCount = files.length;
    const fileNames = fileCount > 0 ? Array.from(files).map(file => file.name).join(', ') : 'No files chosen';
    e.target.nextElementSibling.textContent = `${fileCount} file(s) chosen: ${fileNames}`; // Show file count and names
});

downloadButton.addEventListener('click', async () => {
    window.location.href = '/download_excel';
});

referenceCanvas.addEventListener('click', (event) => handleCanvasClick(event));

function handleCanvasClick(event) {
    const rect = referenceCanvas.getBoundingClientRect();
    const x = (event.clientX - rect.left) * (referenceCanvas.width / rect.width);
    const y = (event.clientY - rect.top) * (referenceCanvas.height / rect.height);

    if (!pointA) {
        pointA = { x: x, y: y };
        drawPoint(refCtx, x, y, 'green');
        
        // Draw points on all sample canvases
        currentSamples.forEach((_, index) => {
            const sampleCanvas = document.getElementById(`sampleCanvas_${index}`);
            const sampleCtx = sampleCanvas.getContext('2d');
            drawPoint(sampleCtx, x, y, 'green');
        });
    } else {
        pointB = { x: x, y: y };
        drawPoint(refCtx, x, y, 'blue');
        drawLine(refCtx, pointA, pointB);
        
        // Draw points and lines on all sample canvases
        currentSamples.forEach((_, index) => {
            const sampleCanvas = document.getElementById(`sampleCanvas_${index}`);
            const sampleCtx = sampleCanvas.getContext('2d');
            drawPoint(sampleCtx, x, y, 'blue');
            drawLine(sampleCtx, pointA, pointB);
        });

        analyzeLine(pointA, pointB);
        pointA = null;
        pointB = null;
    }
}

let currentSlideIndex = 0;

function updateSlideIndicator() {
    const total = currentSamples.length;
    document.getElementById('slideIndicator').textContent = `${currentSlideIndex + 1}/${total}`;
}

function showSlide(index) {
    // Hide all slides
    document.querySelectorAll('.slide').forEach(slide => {
        slide.classList.remove('active');
    });
    
    // Show current slide
    document.querySelector(`#sampleCanvas_${index}`).parentElement.classList.add('active');
    document.querySelector(`#sampleProfile_${index}`).classList.add('active');
    
    // Update navigation buttons
    const prevButton = document.getElementById('prevSlide');
    const nextButton = document.getElementById('nextSlide');
    
    prevButton.disabled = index === 0;
    nextButton.disabled = index === currentSamples.length - 1;
    
    currentSlideIndex = index;
    updateSlideIndicator();
}

function createSampleCanvas(index) {
    const container = document.createElement('div');
    container.className = 'slide image-container';
    if (index === 0) container.classList.add('active');
    container.innerHTML = `
        <h3>Sample Image ${index + 1}</h3>
        <canvas id="sampleCanvas_${index}"></canvas>
        <div id="samplePointInfo_${index}" class="point-info"></div>
    `;
    document.getElementById('sampleImagesContainer').appendChild(container);
    return document.getElementById(`sampleCanvas_${index}`);
}

function createSampleProfile(index) {
    const container = document.createElement('div');
    container.className = 'slide sample-profile';
    if (index === 0) container.classList.add('active');
    container.id = `sampleProfile_${index}`;
    container.innerHTML = `
        <h3>Sample ${index + 1} Line Profile</h3>
        <img id="sampleProfileImage_${index}" class="profile-image" />
    `;
    document.getElementById('sampleProfiles').appendChild(container);
}


// Add event listeners for slider navigation
document.getElementById('prevSlide').addEventListener('click', () => {
    if (currentSlideIndex > 0) {
        showSlide(currentSlideIndex - 1);
    }
});

document.getElementById('nextSlide').addEventListener('click', () => {
    if (currentSlideIndex < currentSamples.length - 1) {
        showSlide(currentSlideIndex + 1);
    }
});

// Modify the upload form event listener
document.getElementById('uploadForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    const formData = new FormData();
    
    // Add reference image
    const referenceFile = this.reference.files[0];
    formData.append('reference', referenceFile);
    
    // Add sample images
    const sampleFiles = this.samples.files;
    for (let i = 0; i < sampleFiles.length; i++) {
        formData.append('samples', sampleFiles[i]);
    }

    try {
        const response = await fetch('/upload', { method: 'POST', body: formData });
        const data = await response.json();
        
        // Clear previous content
        document.getElementById('sampleImagesContainer').innerHTML = '';
        document.getElementById('sampleProfiles').innerHTML = '';
        downloadButton.style.display = 'none';
        currentSlideIndex = 0;
        
        // Load reference image
        referenceImage = new Image();
        referenceImage.onload = () => {
            referenceCanvas.width = referenceImage.width;
            referenceCanvas.height = referenceImage.height;
            refCtx.drawImage(referenceImage, 0, 0);
        };
        referenceImage.src = data.reference;
        
        // Load sample images
        currentSamples = data.samples;
        currentSamples.forEach((sampleSrc, index) => {
            const sampleCanvas = createSampleCanvas(index);
            const sampleCtx = sampleCanvas.getContext('2d');
            
            const sampleImage = new Image();
            sampleImage.onload = () => {
                sampleCanvas.width = sampleImage.width;
                sampleCanvas.height = sampleImage.height;
                sampleCtx.drawImage(sampleImage, 0, 0);
            };
            sampleImage.src = sampleSrc;
            
            createSampleProfile(index);
        });
        
        updateSlideIndicator();
        
    } catch (error) {
        console.error('Upload error:', error);
    }
});
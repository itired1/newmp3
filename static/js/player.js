// Music Player

class Player {
    static init() {
        this.audio = new Audio();
        this.queue = [];
        this.currentTrackIndex = -1;
        this.isPlaying = false;
        this.isShuffled = false;
        this.repeatMode = 'none'; // none, one, all
        this.volume = 0.8;
        this.currentTime = 0;
        this.duration = 0;
        
        // Initialize UI elements
        this.playBtn = document.getElementById('play-btn');
        this.prevBtn = document.getElementById('prev-btn');
        this.nextBtn = document.getElementById('next-btn');
        this.repeatBtn = document.getElementById('repeat-btn');
        this.shuffleBtn = document.getElementById('shuffle-btn');
        this.volumeSlider = document.getElementById('volume-slider');
        this.volumeIcon = document.getElementById('volume-icon');
        this.progressBar = document.getElementById('progress-bar');
        this.progressFill = document.getElementById('progress-fill');
        this.timeCurrent = document.getElementById('time-current');
        this.timeTotal = document.getElementById('time-total');
        this.trackTitle = document.getElementById('track-title');
        this.trackArtist = document.getElementById('track-artist');
        this.trackCover = document.getElementById('track-cover');
        
        // Initialize event listeners
        this.initEventListeners();
        
        // Restore volume from localStorage
        const savedVolume = localStorage.getItem('player_volume');
        if (savedVolume !== null) {
            this.volume = parseFloat(savedVolume);
            this.audio.volume = this.volume;
            if (this.volumeSlider) {
                this.volumeSlider.value = this.volume * 100;
                this.updateVolumeIcon();
            }
        }
        
        console.log('Music Player initialized');
    }
    
    static initEventListeners() {
        // Play/Pause button
        if (this.playBtn) {
            this.playBtn.addEventListener('click', () => {
                this.togglePlay();
            });
        }
        
        // Previous track
        if (this.prevBtn) {
            this.prevBtn.addEventListener('click', () => {
                this.prevTrack();
            });
        }
        
        // Next track
        if (this.nextBtn) {
            this.nextBtn.addEventListener('click', () => {
                this.nextTrack();
            });
        }
        
        // Repeat button
        if (this.repeatBtn) {
            this.repeatBtn.addEventListener('click', () => {
                this.toggleRepeat();
            });
        }
        
        // Shuffle button
        if (this.shuffleBtn) {
            this.shuffleBtn.addEventListener('click', () => {
                this.toggleShuffle();
            });
        }
        
        // Volume slider
        if (this.volumeSlider) {
            this.volumeSlider.addEventListener('input', (e) => {
                this.setVolume(e.target.value / 100);
            });
        }
        
        // Progress bar click
        if (this.progressBar) {
            this.progressBar.addEventListener('click', (e) => {
                const rect = this.progressBar.getBoundingClientRect();
                const percent = (e.clientX - rect.left) / rect.width;
                this.seekTo(percent * this.duration);
            });
        }
        
        // Audio events
        this.audio.addEventListener('timeupdate', () => {
            this.updateProgress();
        });
        
        this.audio.addEventListener('loadedmetadata', () => {
            this.duration = this.audio.duration;
            this.updateProgress();
            this.updateTimeDisplay();
        });
        
        this.audio.addEventListener('ended', () => {
            this.handleTrackEnd();
        });
        
        this.audio.addEventListener('play', () => {
            this.isPlaying = true;
            this.updatePlayButton();
        });
        
        this.audio.addEventListener('pause', () => {
            this.isPlaying = false;
            this.updatePlayButton();
        });
        
        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            // Space bar to play/pause (except when in input fields)
            if (e.code === 'Space' && !['INPUT', 'TEXTAREA'].includes(document.activeElement.tagName)) {
                e.preventDefault();
                this.togglePlay();
            }
            
            // Left/Right arrows for seeking
            if (e.code === 'ArrowLeft' && e.ctrlKey) {
                e.preventDefault();
                this.seekTo(this.currentTime - 10);
            }
            
            if (e.code === 'ArrowRight' && e.ctrlKey) {
                e.preventDefault();
                this.seekTo(this.currentTime + 10);
            }
            
            // M to mute
            if (e.code === 'KeyM') {
                e.preventDefault();
                this.toggleMute();
            }
            
            // F to toggle fullscreen (if implemented)
            if (e.code === 'KeyF' && e.ctrlKey) {
                e.preventDefault();
                this.toggleFullscreen();
            }
        });
    }
    
    static async playTrack(service, trackId, autoPlay = true) {
        try {
            // Show loading state
            this.showLoading();
            
            // Get track URL from API
            const trackData = await API.getTrackUrl(service, trackId);
            
            if (!trackData.url) {
                throw new Error('Track URL not found');
            }
            
            // Create track object
            const track = {
                id: `${service}_${trackId}`,
                service,
                trackId,
                url: trackData.url,
                title: trackData.title,
                artists: trackData.artists,
                coverUri: trackData.cover_uri,
                duration: trackData.duration
            };
            
            // Add to queue if not already playing
            if (this.queue.length === 0 || this.currentTrackIndex === -1) {
                this.queue = [track];
                this.currentTrackIndex = 0;
            } else if (!this.queue.some(t => t.id === track.id)) {
                this.queue.push(track);
            }
            
            // Play the track
            this.loadTrack(track);
            
            if (autoPlay) {
                await this.audio.play();
                this.isPlaying = true;
                this.updatePlayButton();
            }
            
            // Update UI
            this.updateTrackInfo(track);
            
            // Create visual effect
            Utils.createMusicNotes(5);
            
        } catch (error) {
            console.error('Error playing track:', error);
            Utils.toast('Ошибка воспроизведения трека', 'error');
            this.hideLoading();
        }
    }
    
    static loadTrack(track) {
        this.audio.src = track.url;
        this.audio.load();
        
        // Update track info
        this.updateTrackInfo(track);
        
        // Save to recently played
        this.saveToHistory(track);
    }
    
    static updateTrackInfo(track) {
        if (this.trackTitle) {
            this.trackTitle.textContent = track.title;
        }
        
        if (this.trackArtist) {
            this.trackArtist.textContent = Array.isArray(track.artists) 
                ? track.artists.join(', ') 
                : track.artists;
        }
        
        if (this.trackCover) {
            const img = this.trackCover.querySelector('img');
            if (img) {
                img.src = track.coverUri || '/static/assets/images/default-cover.png';
                img.alt = track.title;
            }
        }
        
        if (this.timeTotal) {
            this.timeTotal.textContent = Utils.formatTrackDuration(track.duration);
        }
    }
    
    static togglePlay() {
        if (this.audio.src) {
            if (this.isPlaying) {
                this.audio.pause();
            } else {
                this.audio.play();
            }
        }
    }
    
    static updatePlayButton() {
        if (!this.playBtn) return;
        
        const icon = this.playBtn.querySelector('i');
        if (icon) {
            icon.className = this.isPlaying ? 'fas fa-pause' : 'fas fa-play';
        }
    }
    
    static prevTrack() {
        if (this.queue.length === 0) return;
        
        if (this.currentTime > 3) {
            // If more than 3 seconds into track, restart it
            this.seekTo(0);
        } else {
            // Otherwise go to previous track
            this.currentTrackIndex--;
            
            if (this.currentTrackIndex < 0) {
                if (this.repeatMode === 'all') {
                    this.currentTrackIndex = this.queue.length - 1;
                } else {
                    this.currentTrackIndex = 0;
                    return;
                }
            }
            
            const track = this.queue[this.currentTrackIndex];
            this.loadTrack(track);
            this.audio.play();
        }
    }
    
    static nextTrack() {
        if (this.queue.length === 0) return;
        
        this.currentTrackIndex++;
        
        if (this.currentTrackIndex >= this.queue.length) {
            if (this.repeatMode === 'all') {
                this.currentTrackIndex = 0;
            } else {
                // Stop at the end
                this.currentTrackIndex = this.queue.length - 1;
                this.audio.pause();
                return;
            }
        }
        
        const track = this.queue[this.currentTrackIndex];
        this.loadTrack(track);
        this.audio.play();
    }
    
    static handleTrackEnd() {
        switch (this.repeatMode) {
            case 'one':
                // Repeat same track
                this.audio.currentTime = 0;
                this.audio.play();
                break;
            case 'all':
                // Go to next track or loop to start
                this.nextTrack();
                break;
            case 'none':
            default:
                // Go to next track or stop
                this.nextTrack();
                break;
        }
    }
    
    static toggleRepeat() {
        const modes = ['none', 'one', 'all'];
        const currentIndex = modes.indexOf(this.repeatMode);
        this.repeatMode = modes[(currentIndex + 1) % modes.length];
        
        // Update button appearance
        if (this.repeatBtn) {
            const icon = this.repeatBtn.querySelector('i');
            if (icon) {
                switch (this.repeatMode) {
                    case 'one':
                        icon.style.color = 'var(--accent-primary)';
                        this.repeatBtn.classList.add('active');
                        Utils.toast('Повтор одного трека', 'info');
                        break;
                    case 'all':
                        icon.style.color = 'var(--accent-primary)';
                        this.repeatBtn.classList.add('active');
                        Utils.toast('Повтор плейлиста', 'info');
                        break;
                    default:
                        icon.style.color = '';
                        this.repeatBtn.classList.remove('active');
                        break;
                }
            }
        }
    }
    
    static toggleShuffle() {
        this.isShuffled = !this.isShuffled;
        
        if (this.isShuffled && this.queue.length > 1) {
            // Shuffle the queue (excluding current track)
            const currentTrack = this.queue[this.currentTrackIndex];
            const otherTracks = this.queue.filter((_, i) => i !== this.currentTrackIndex);
            
            // Fisher-Yates shuffle
            for (let i = otherTracks.length - 1; i > 0; i--) {
                const j = Math.floor(Math.random() * (i + 1));
                [otherTracks[i], otherTracks[j]] = [otherTracks[j], otherTracks[i]];
            }
            
            this.queue = [currentTrack, ...otherTracks];
            this.currentTrackIndex = 0;
            
            Utils.toast('Плейлист перемешан', 'success');
        }
        
        // Update button appearance
        if (this.shuffleBtn) {
            if (this.isShuffled) {
                this.shuffleBtn.classList.add('active');
            } else {
                this.shuffleBtn.classList.remove('active');
            }
        }
    }
    
    static setVolume(value) {
        this.volume = Math.max(0, Math.min(1, value));
        this.audio.volume = this.volume;
        
        // Save to localStorage
        localStorage.setItem('player_volume', this.volume);
        
        // Update volume icon
        this.updateVolumeIcon();
    }
    
    static updateVolumeIcon() {
        if (!this.volumeIcon) return;
        
        if (this.volume === 0) {
            this.volumeIcon.className = 'fas fa-volume-mute';
        } else if (this.volume < 0.5) {
            this.volumeIcon.className = 'fas fa-volume-down';
        } else {
            this.volumeIcon.className = 'fas fa-volume-up';
        }
    }
    
    static toggleMute() {
        if (this.audio.muted) {
            this.audio.muted = false;
            this.volumeIcon.className = 'fas fa-volume-up';
        } else {
            this.audio.muted = true;
            this.volumeIcon.className = 'fas fa-volume-mute';
        }
    }
    
    static seekTo(time) {
        this.audio.currentTime = Math.max(0, Math.min(this.duration, time));
        this.updateProgress();
    }
    
    static updateProgress() {
        if (!this.audio) return;
        
        this.currentTime = this.audio.currentTime;
        this.duration = this.audio.duration || 0;
        
        const percent = this.duration > 0 ? (this.currentTime / this.duration) * 100 : 0;
        
        // Update progress bar
        if (this.progressFill) {
            this.progressFill.style.width = `${percent}%`;
        }
        
        // Update time display
        this.updateTimeDisplay();
    }
    
    static updateTimeDisplay() {
        if (this.timeCurrent) {
            this.timeCurrent.textContent = Utils.formatTime(this.currentTime);
        }
        
        if (this.timeTotal && this.duration > 0) {
            this.timeTotal.textContent = Utils.formatTime(this.duration);
        }
    }
    
    static showLoading() {
        // Add loading animation to play button
        if (this.playBtn) {
            const icon = this.playBtn.querySelector('i');
            if (icon) {
                icon.className = 'fas fa-spinner fa-spin';
            }
        }
        
        // Show loading state on track cover
        if (this.trackCover) {
            this.trackCover.classList.add('loading');
        }
    }
    
    static hideLoading() {
        // Restore play button
        this.updatePlayButton();
        
        // Remove loading state from track cover
        if (this.trackCover) {
            this.trackCover.classList.remove('loading');
        }
    }
    
    static saveToHistory(track) {
        // In a real app, this would save to server via API
        // For now, just update local storage for demo
        
        const history = JSON.parse(localStorage.getItem('recent_tracks') || '[]');
        
        // Remove if already exists
        const existingIndex = history.findIndex(item => item.id === track.id);
        if (existingIndex !== -1) {
            history.splice(existingIndex, 1);
        }
        
        // Add to beginning
        history.unshift({
            id: track.id,
            title: track.title,
            artists: track.artists,
            coverUri: track.coverUri,
            playedAt: new Date().toISOString()
        });
        
        // Keep only last 50 tracks
        if (history.length > 50) {
            history.pop();
        }
        
        localStorage.setItem('recent_tracks', JSON.stringify(history));
    }
    
    static toggleFullscreen() {
        const player = document.getElementById('music-player');
        if (!player) return;
        
        if (!document.fullscreenElement) {
            player.requestFullscreen?.();
        } else {
            document.exitFullscreen?.();
        }
    }
    
    static addToQueue(tracks) {
        if (!Array.isArray(tracks)) {
            tracks = [tracks];
        }
        
        this.queue.push(...tracks);
        Utils.toast(`Добавлено ${tracks.length} треков в очередь`, 'success');
    }
    
    static clearQueue() {
        this.queue = [];
        this.currentTrackIndex = -1;
        this.audio.src = '';
        this.audio.pause();
        
        // Reset UI
        if (this.trackTitle) this.trackTitle.textContent = 'Не играет';
        if (this.trackArtist) this.trackArtist.textContent = 'Выберите трек';
        if (this.trackCover) {
            const img = this.trackCover.querySelector('img');
            if (img) img.src = '';
        }
        
        this.updatePlayButton();
        this.updateProgress();
    }
    
    static getCurrentTrack() {
        if (this.currentTrackIndex >= 0 && this.currentTrackIndex < this.queue.length) {
            return this.queue[this.currentTrackIndex];
        }
        return null;
    }
    
    static getQueue() {
        return [...this.queue];
    }
    
    static getQueueLength() {
        return this.queue.length;
    }
}

// Initialize player when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    Player.init();
});

// Make Player available globally
window.Player = Player;
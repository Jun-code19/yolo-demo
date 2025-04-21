import axios from 'axios';

const BASE_URL = '/api/v2/detection';

export const startDetection = async (configId) => {
    try {
        const response = await axios.post(`${BASE_URL}/${configId}/start`);
        return response.data;
    } catch (error) {
        // console.error('启动检测任务失败:', error);
        throw error;
    }
};

export const stopDetection = async (configId) => {
    try {
        const response = await axios.post(`${BASE_URL}/${configId}/stop`);
        return response.data;
    } catch (error) {
        // console.error('停止检测任务失败:', error);
        throw error;
    }
};

export const getDetectionStatus = async () => {
    try {
        const response = await axios.get(`${BASE_URL}/status`);
        return response.data;
    } catch (error) {
        // console.error('获取检测任务状态失败:', error);
        throw error;
    }
};
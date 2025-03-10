import torch
import torch.nn.functional as F
import cv2 as cv
import numpy as np
import os
from glob import glob
from icecream import ic
import imageio 
import json
from scipy.spatial.transform import Rotation as Rot
from scipy.spatial.transform import Slerp


class BlenderDataset:
    def __init__(self, conf):
        super(BlenderDataset, self).__init__()
        print('Load data: Begin')
        self.device = torch.device('cuda')
        self.conf = conf

        self.data_dir = conf.get_string('data_dir')
    
        metas = {}
        with open(os.path.join(self.data_dir, 'transforms_{}.json'.format('train')), 'r') as fp:
            metas['train'] = json.load(fp)

        all_imgs = []
        all_masks = []
        all_poses = []
        counts = [0]
 
        # x -> x
        # y -> -y
        # z -> -z
        T = np.eye(4)
        T[0, 0] = 1
        T[1, 1] = -1
        T[2, 2] = -1
        
        meta = metas['train']
        imgs = []
        masks = []
        poses = []
        self.images_lis = []
        for frame in meta['frames'][::1]:
            fname = os.path.join(self.data_dir, frame['file_path'] + '.png')
            self.images_lis.append(fname)
            img = cv.imread(fname, flags=cv.IMREAD_UNCHANGED)
            imgs.append(img)
            # get alpha channel
            mask = img[:, :, 3] # alpha channel
            mask = np.expand_dims(mask, axis=-1)
            # threshold mask
            mask = (mask > 0).astype(np.float32)
            masks.append(mask)
            pose = np.array(frame['transform_matrix'])
            pose = pose @ T
            poses.append(pose)
        imgs = (np.array(imgs) / 255.).astype(np.float32) # RGB
        poses = np.array(poses).astype(np.float32)
        counts.append(counts[-1] + imgs.shape[0])
        all_imgs.append(imgs)
        all_masks.append(masks)
        all_poses.append(poses)
        
        imgs = np.concatenate(all_imgs, 0)
        imgs = imgs[...,:3]*imgs[...,-1:] # + (1.-imgs[...,-1:])
        masks = np.concatenate(all_masks, 0)
        poses = np.concatenate(all_poses, 0)

        # self.render_cameras_name = conf.get_string('render_cameras_name')
        # self.object_cameras_name = conf.get_string('object_cameras_name')

        # self.camera_outside_sphere = conf.get_bool('camera_outside_sphere', default=True)
        # self.scale_mat_scale = conf.get_float('scale_mat_scale', default=1.1)

        # camera_dict = np.load(os.path.join(self.data_dir, self.render_cameras_name))
        # self.camera_dict = camera_dict
        # self.images_lis = sorted(glob(os.path.join(self.data_dir, 'train/*.png')))
        # self.images_np = np.stack([cv.imread(im_name) for im_name in self.images_lis]) / 256.0
        # self.images_np = self.images_np[...,:3]*self.images_np[...,-1:] + (1.-self.images_np[...,-1:])
        
        # self.masks_lis = sorted(glob(os.path.join(self.data_dir, 'mask/*.png')))
        # self.masks_np = np.stack([cv.imread(im_name) for im_name in self.masks_lis]) / 256.0

        # world_mat is a projection matrix from world to image
        # self.world_mats_np = [camera_dict['world_mat_%d' % idx].astype(np.float32) for idx in range(self.n_images)]

        # self.scale_mats_np = []

        # scale_mat: used for coordinate normalization, we assume the scene to render is inside a unit sphere at origin.
        # self.scale_mats_np = [camera_dict['scale_mat_%d' % idx].astype(np.float32) for idx in range(self.n_images)]

        # self.intrinsics_all = []
        # self.pose_all = []
        # self.pose_all.append(torch.zeros(4, 4))

        # for scale_mat, world_mat in zip(self.scale_mats_np, self.world_mats_np):
        #     P = world_mat @ scale_mat
        #     P = P[:3, :4]
        #     intrinsics, pose = load_K_Rt_from_P(None, P)
        #     self.intrinsics_all.append(torch.from_numpy(intrinsics).float())
        #     self.pose_all.append(torch.from_numpy(pose).float())

        # self.masks  = torch.from_numpy(self.masks_np.astype(np.float32)).cpu()   # [n_images, H, W, 3]
        # self.intrinsics_all = torch.stack(self.intrinsics_all).to(self.device)   # [n_images, 4, 4]
        # self.intrinsics_all_inv = torch.inverse(self.intrinsics_all)  # [n_images, 4, 4]
        # self.focal = self.intrinsics_all[0][0, 0]

        self.images = torch.from_numpy(imgs.astype(np.float32)).cpu()  # [n_images, H, W, 3]
        self.masks = torch.from_numpy(masks.astype(np.float32)).cpu()  # [n_images, H, W, 1]
        self.n_images = self.images.shape[0]
        self.pose_all = torch.from_numpy(poses).float().to(self.device) # [n_images, 4, 4]
    
        # print("images.shape", self.images.shape)
        # print("masks.shape", self.masks.shape)

        # Scaling (we assume the scene to render is inside a unit sphere at origin)        
        vectors_norms = torch.norm(self.pose_all[:, :3, 3], dim=1)
        scale = 1 / torch.max(vectors_norms).item()
        # scale all vectors
        self.pose_all[:, :3, 3] *= scale

        self.H, self.W = self.images.shape[1], self.images.shape[2]

        camera_angle_x = float(meta['camera_angle_x'])
        focal = .5 * self.W / np.tan(.5 * camera_angle_x)
        self.focal = torch.tensor(focal).to(self.device) 
        self.image_pixels = self.H * self.W

        intrinsics = np.eye(4)
        intrinsics[0, 0] = self.focal
        intrinsics[1, 1] = self.focal
        intrinsics[0, 2] = .5 * self.W
        intrinsics[1, 2] = .5 * self.H
        intrinsics_inv = np.linalg.inv(intrinsics)
        intrinsics = np.expand_dims(intrinsics, axis=0)
        intrinsics_inv = np.expand_dims(intrinsics_inv, axis=0)
        self.intrinsics_all = np.repeat(intrinsics, self.n_images, axis=0)
        self.intrinsics_all = torch.from_numpy(self.intrinsics_all).float().to(self.device)   
        self.intrinsics_all_inv = np.repeat(intrinsics_inv, self.n_images, axis=0)
        self.intrinsics_all_inv = torch.from_numpy(self.intrinsics_all_inv).float().to(self.device)

        # Object scale mat: region of interest to **extract mesh**
        self.object_bbox_min = np.array([-1.01, -1.01, -1.01])
        self.object_bbox_max = np.array([1.01, 1.01, 1.01])
        print('Load data: End')

    def gen_rays_at(self, img_idx, resolution_level=1):
        """
        Generate rays at world space from one camera.
        """
        l = resolution_level
        tx = torch.linspace(0, self.W - 1, self.W // l)
        ty = torch.linspace(0, self.H - 1, self.H // l)
        pixels_x, pixels_y = torch.meshgrid(tx, ty)
        p = torch.stack([pixels_x, pixels_y, torch.ones_like(pixels_y)], dim=-1) # W, H, 3
        p = torch.matmul(self.intrinsics_all_inv[img_idx, None, None, :3, :3], p[:, :, :, None]).squeeze()  # W, H, 3
        rays_v = p / torch.linalg.norm(p, ord=2, dim=-1, keepdim=True)  # W, H, 3
        rays_v = torch.matmul(self.pose_all[img_idx, None, None, :3, :3], rays_v[:, :, :, None]).squeeze()  # W, H, 3
        rays_o = self.pose_all[img_idx, None, None, :3, 3].expand(rays_v.shape)  # W, H, 3
        return rays_o.transpose(0, 1), rays_v.transpose(0, 1)

    def gen_random_rays_at(self, img_idx, batch_size):
        """
        Generate random rays at world space from one camera.
        """
        pixels_x = torch.randint(low=0, high=self.W, size=[batch_size]).cpu()
        pixels_y = torch.randint(low=0, high=self.H, size=[batch_size]).cpu()
        color = self.images[img_idx][(pixels_y, pixels_x)]    # batch_size, 3
        mask = self.masks[img_idx][(pixels_y, pixels_x)]      # batch_size, 3
        p = torch.stack([pixels_x, pixels_y, torch.ones_like(pixels_y)], dim=-1).float()  # batch_size, 3
        p = torch.matmul(self.intrinsics_all_inv[img_idx, None, :3, :3].cpu(), p[:, :, None]).squeeze() # batch_size, 3
        rays_v = p / torch.linalg.norm(p, ord=2, dim=-1, keepdim=True)    # batch_size, 3
        rays_v = torch.matmul(self.pose_all[img_idx, None, :3, :3].cpu(), rays_v[:, :, None]).squeeze().cpu()  # batch_size, 3
        rays_o = self.pose_all[img_idx, None, :3, 3].expand(rays_v.shape).cpu() # batch_size, 3
        return torch.cat([rays_o, rays_v, color, mask[:, :1]], dim=-1).cuda()    # batch_size, 10

    def gen_rays_between(self, idx_0, idx_1, ratio, resolution_level=1):
        """
        Interpolate pose between two cameras.
        """
        l = resolution_level
        tx = torch.linspace(0, self.W - 1, self.W // l)
        ty = torch.linspace(0, self.H - 1, self.H // l)
        pixels_x, pixels_y = torch.meshgrid(tx, ty)
        p = torch.stack([pixels_x, pixels_y, torch.ones_like(pixels_y)], dim=-1)  # W, H, 3
        p = torch.matmul(self.intrinsics_all_inv[0, None, None, :3, :3], p[:, :, :, None]).squeeze()  # W, H, 3
        rays_v = p / torch.linalg.norm(p, ord=2, dim=-1, keepdim=True)  # W, H, 3
        trans = self.pose_all[idx_0, :3, 3] * (1.0 - ratio) + self.pose_all[idx_1, :3, 3] * ratio
        pose_0 = self.pose_all[idx_0].detach().cpu().numpy()
        pose_1 = self.pose_all[idx_1].detach().cpu().numpy()
        pose_0 = np.linalg.inv(pose_0)
        pose_1 = np.linalg.inv(pose_1)
        rot_0 = pose_0[:3, :3]
        rot_1 = pose_1[:3, :3]
        rots = Rot.from_matrix(np.stack([rot_0, rot_1]))
        key_times = [0, 1]
        slerp = Slerp(key_times, rots)
        rot = slerp(ratio)
        pose = np.diag([1.0, 1.0, 1.0, 1.0])
        pose = pose.astype(np.float32)
        pose[:3, :3] = rot.as_matrix()
        pose[:3, 3] = ((1.0 - ratio) * pose_0 + ratio * pose_1)[:3, 3]
        pose = np.linalg.inv(pose)
        rot = torch.from_numpy(pose[:3, :3]).cuda()
        trans = torch.from_numpy(pose[:3, 3]).cuda()
        rays_v = torch.matmul(rot[None, None, :3, :3], rays_v[:, :, :, None]).squeeze()  # W, H, 3
        rays_o = trans[None, None, :3].expand(rays_v.shape)  # W, H, 3
        return rays_o.transpose(0, 1), rays_v.transpose(0, 1)

    def near_far_from_sphere(self, rays_o, rays_d):
        a = torch.sum(rays_d**2, dim=-1, keepdim=True)
        b = 2.0 * torch.sum(rays_o * rays_d, dim=-1, keepdim=True)
        mid = 0.5 * (-b) / a
        near = mid - 1.0
        far = mid + 1.0
        return near, far

    def image_at(self, idx, resolution_level):
        img = cv.imread(self.images_lis[idx])
        return (cv.resize(img, (self.W // resolution_level, self.H // resolution_level))).clip(0, 255)

